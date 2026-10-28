//! GIO supplies XDG precedence, locale, desktop filtering and Exec semantics.
use gio::prelude::*;
use gtk::prelude::*;
use serde::Serialize;
use std::{
    path::Path,
    sync::Mutex,
    time::{Duration, Instant},
};
use tauri::{AppHandle, Emitter, Manager};

// GIO/GTK objects belong to the GTK main context, rather than Tauri's Send state.
// Retain the monitor: connect_changed alone does not retain its GObject.
thread_local! {
    static WATCHES: std::cell::RefCell<Option<CatalogueWatches>> = const { std::cell::RefCell::new(None) };
}
struct AppInfoWatch {
    monitor: gio::AppInfoMonitor,
    handler: Option<gio::glib::SignalHandlerId>,
}
impl AppInfoWatch {
    fn new(changed: impl Fn() + 'static) -> Self {
        let monitor = gio::AppInfoMonitor::get();
        let handler = monitor.connect_changed(move |_| changed());
        Self {
            monitor,
            handler: Some(handler),
        }
    }
}
impl Drop for AppInfoWatch {
    fn drop(&mut self) {
        if let Some(handler) = self.handler.take() {
            self.monitor.disconnect(handler);
        }
    }
}
struct CatalogueWatches {
    _applications: AppInfoWatch,
    theme: Option<(gtk::IconTheme, gio::glib::SignalHandlerId)>,
}
impl Drop for CatalogueWatches {
    fn drop(&mut self) {
        if let Some((theme, handler)) = self.theme.take() {
            theme.disconnect(handler);
        }
    }
}

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct InstalledApp {
    id: String,
    name: String,
    generic_name: String,
    keywords: Vec<String>,
    executable: String,
    match_classes: Vec<String>,
    icon_path: Option<String>,
    actions: Vec<DesktopAction>,
}
#[derive(Clone, Serialize)]
pub struct DesktopAction {
    id: String,
    name: String,
}
#[derive(Default)]
pub struct Catalogue {
    apps: Vec<InstalledApp>,
    refreshed: Option<Instant>,
    dirty: bool,
}
#[derive(Default)]
pub struct AppCatalogue(pub Mutex<Catalogue>);

fn describe(app: gio::DesktopAppInfo) -> Option<InstalledApp> {
    describe_with_icon(app, |icon| {
        gtk::IconTheme::default()
            .and_then(|theme| theme.lookup_by_gicon(icon, 64, gtk::IconLookupFlags::FORCE_SIZE))
            .and_then(|info| info.filename())
            .map(|p| p.to_string_lossy().into_owned())
    })
}
fn describe_with_icon(
    app: gio::DesktopAppInfo,
    resolve_icon: impl FnOnce(&gio::Icon) -> Option<String>,
) -> Option<InstalledApp> {
    if app.is_hidden() || !app.should_show() {
        return None;
    }
    let id = app.id()?.to_string();
    let executable = app.executable().to_string_lossy().into_owned();
    let mut match_classes = vec![id.trim_end_matches(".desktop").to_lowercase()];
    if let Some(class) = app.startup_wm_class() {
        match_classes.push(class.to_lowercase());
    }
    if let Some(name) = Path::new(&executable)
        .file_name()
        .and_then(|v| v.to_str())
        .filter(|n| !matches!(*n, "env" | "flatpak" | "snap"))
    {
        match_classes.push(name.to_lowercase());
    }
    match_classes.sort();
    match_classes.dedup();
    let icon_path = app.icon().and_then(|icon| resolve_icon(&icon));
    let actions = app
        .list_actions()
        .into_iter()
        .map(|id| DesktopAction {
            name: app.action_name(&id).into(),
            id: id.into(),
        })
        .collect();
    Some(InstalledApp {
        id,
        name: app.display_name().into(),
        generic_name: app.generic_name().map(String::from).unwrap_or_default(),
        keywords: app.keywords().into_iter().map(String::from).collect(),
        executable,
        match_classes,
        icon_path,
        actions,
    })
}
#[tauri::command]
pub fn get_installed_apps(
    app: AppHandle,
    state: tauri::State<AppCatalogue>,
    refresh: Option<bool>,
) -> Result<Vec<InstalledApp>, String> {
    let mut cache = state.0.lock().map_err(|e| e.to_string())?;
    if refresh == Some(true)
        || cache.dirty
        || cache
            .refreshed
            .is_none_or(|t| t.elapsed() > Duration::from_secs(30))
    {
        cache.apps = gio::AppInfo::all()
            .into_iter()
            .filter_map(|app| app.downcast::<gio::DesktopAppInfo>().ok())
            .filter_map(describe)
            .collect();
        cache.apps.sort_by(|a, b| {
            a.name
                .to_lowercase()
                .cmp(&b.name.to_lowercase())
                .then_with(|| a.id.cmp(&b.id))
        });
        cache.refreshed = Some(Instant::now());
        cache.dirty = false;
    }
    for info in &cache.apps {
        if let Some(path) = &info.icon_path {
            app.asset_protocol_scope()
                .allow_file(path)
                .map_err(|e| e.to_string())?;
        }
    }
    Ok(cache.apps.clone())
}
#[tauri::command]
pub fn launch_installed_app(id: String, action: Option<String>) -> Result<bool, String> {
    launch_desktop_entry(&id, action.as_deref())
}
fn launch_desktop_entry(id: &str, action: Option<&str>) -> Result<bool, String> {
    let app = gio::DesktopAppInfo::new(&id)
        .ok_or("app_missing: Ứng dụng đã bị gỡ hoặc không thể khởi chạy")?;
    if app.is_hidden() || !app.should_show() {
        return Err("app_hidden: Ứng dụng không được hiển thị trong môi trường hiện tại".into());
    }
    if let Some(action) = action {
        if !app.list_actions().iter().any(|id| id == &action) {
            return Err("app_action_missing: Hành động không còn khả dụng".into());
        }
        app.launch_action(action, None::<&gio::AppLaunchContext>);
    } else {
        app.launch(&[], None::<&gio::AppLaunchContext>)
            .map_err(|e| format!("app_launch_failed: {e}"))?;
    }
    Ok(true)
}
pub fn watch(app: &AppHandle) {
    let handle = app.clone();
    let changed = std::rc::Rc::new(move || {
        if let Ok(mut state) = handle.state::<AppCatalogue>().0.lock() {
            state.dirty = true;
        }
        let _ = handle.emit("deskmorph:apps-changed", ());
    });
    let callback = changed.clone();
    let applications = AppInfoWatch::new(move || callback());
    let theme = gtk::IconTheme::default().map(|theme| {
        let handler = theme.connect_changed(move |_| changed());
        (theme, handler)
    });
    WATCHES.with(|watches| {
        *watches.borrow_mut() = Some(CatalogueWatches {
            _applications: applications,
            theme,
        })
    });
}
pub fn stop_watching() {
    WATCHES.with(|watches| watches.borrow_mut().take());
}

#[cfg(test)]
#[path = "application_fixtures.rs"]
mod fixtures;

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn desktop_parser_preserves_actions_locale_hints_and_exec_without_shell() {
        let key = gio::glib::KeyFile::new();
        key.load_from_data("[Desktop Entry]\nType=Application\nName=Sample\nExec=/bin/true %U\nStartupWMClass=SampleClass\nKeywords=editor;code;\nActions=New;\n[Desktop Action New]\nName=New document\nExec=/bin/true\n", gio::glib::KeyFileFlags::NONE).unwrap();
        let app = gio::DesktopAppInfo::from_keyfile(&key).unwrap();
        assert_eq!(app.startup_wm_class().unwrap(), "SampleClass");
        assert_eq!(app.keywords().len(), 2);
        assert_eq!(app.list_actions(), ["New"]);
        assert_eq!(app.action_name("New"), "New document");
        assert!(app.should_show());
        key.set_boolean("Desktop Entry", "NoDisplay", true);
        assert!(!gio::DesktopAppInfo::from_keyfile(&key)
            .unwrap()
            .should_show());
        key.set_boolean("Desktop Entry", "Hidden", true);
        assert!(gio::DesktopAppInfo::from_keyfile(&key).unwrap().is_hidden());
    }
}
