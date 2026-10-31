use crate::geometry;
use std::{sync::Mutex, collections::{HashMap, HashSet}, hash::{Hash, Hasher}};
use gtk::prelude::*;
use tauri::{AppHandle, Emitter, Manager, PhysicalPosition, PhysicalSize};
#[derive(Clone)]
pub struct Preferences {
    monitor: Option<String>,
    width: u32,
    height: u32,
    top: bool,
    hidden: bool,
    pending_position: Option<geometry::Rect>,
    docks: HashMap<String, DockState>,
    enabled: bool,
}
impl Default for Preferences {
    fn default() -> Self {
        Self {
            monitor: None,
            width: 1100,
            height: 52,
            top: false,
            hidden: false,
            pending_position: None,
            docks: HashMap::new(),
            enabled: true,
        }
    }
}
#[derive(Clone, Default)]
struct DockState { width: u32, hidden: bool, pending: Option<geometry::Rect> }
pub fn is_dock(label: &str) -> bool { label == "taskbar" || label.starts_with("taskbar-monitor-") }
pub fn dock(app: &AppHandle, source: Option<&str>) -> Result<tauri::WebviewWindow, String> {
    let label = source.unwrap_or("taskbar");
    if !is_dock(label) { return Err("invalid_dock_source".into()); }
    app.get_webview_window(label).ok_or("Không tìm thấy Dock".into())
}
#[derive(Default)]
pub struct LayoutState(pub Mutex<Preferences>);
thread_local! {
    static TOPOLOGY_WATCH: std::cell::RefCell<Option<gio::glib::SourceId>> = const { std::cell::RefCell::new(None) };
}
pub fn configure(app: &AppHandle, config: &serde_json::Value) -> Result<(), String> {
    let state = app.state::<LayoutState>();
    let mut p = state.0.lock().map_err(|e| e.to_string())?;
    p.enabled = config["enabled"] == true;
    p.monitor = config["monitor"].as_str().map(String::from);
    p.height = config["height"].as_u64().unwrap_or(52) as u32;
    p.top = config["position"] == "top";
    if config["autoHide"] != true {
        p.hidden = false;
        for state in p.docks.values_mut() { state.hidden = false; }
    }
    Ok(())
}
pub fn apply(app: &AppHandle) -> Result<bool, String> {
    let window = app
        .get_webview_window("taskbar")
        .ok_or("Không tìm thấy Dock")?;
    let p = app
        .state::<LayoutState>()
        .0
        .lock()
        .map_err(|e| e.to_string())?
        .clone();
    let monitors = window.available_monitors().map_err(|e| e.to_string())?;
    let preferred = p.monitor.as_ref().and_then(|name| monitors.iter().find(|m| m.name() == Some(name))).cloned();
    let primary = window.primary_monitor().map_err(|e| e.to_string())?.or_else(|| monitors.first().cloned()).ok_or("Không tìm thấy màn hình")?;
    let all = p.monitor.as_deref() == Some("*") && crate::platform::dock_placement_available();
    let mut targets = vec![("taskbar".to_string(), preferred.unwrap_or(primary.clone()))];
    if all {
        for monitor in &monitors {
            if monitor.position() == primary.position() { continue; }
            let mut hash = std::collections::hash_map::DefaultHasher::new();
            (monitor.name(), monitor.position().x, monitor.position().y).hash(&mut hash);
            targets.push((format!("taskbar-monitor-{:x}", hash.finish()), monitor.clone()));
        }
    }
    let wanted: HashSet<_> = targets.iter().map(|(label, _)| label.clone()).collect();
    for (label, extra) in app.webview_windows() {
        if is_dock(&label) && !wanted.contains(&label) {
            extra.destroy().map_err(|e| e.to_string())?;
            app.state::<LayoutState>().0.lock().map_err(|e| e.to_string())?.docks.remove(&label);
        }
    }
    for (label, monitor) in targets {
        let created = app.get_webview_window(&label).is_none();
        let window = if let Some(window) = app.get_webview_window(&label) { window } else {
            let window = tauri::WebviewWindowBuilder::new(app, &label,
                tauri::WebviewUrl::App(format!("index.html?window=taskbar&dock={label}").into()))
                .title("DeskMorph Taskbar").inner_size(220., 52.)
                .decorations(false).transparent(true).shadow(false).always_on_top(true)
                .skip_taskbar(true).resizable(true).focused(false).visible(false)
                .build().map_err(|e| e.to_string())?;
            window.gtk_window().map_err(|e| e.to_string())?.set_focus_on_map(false);
            crate::popup::install_window_keyboard(app, &window)?;
            window
        };
        let state = p.docks.get(&label).cloned().unwrap_or_default();
        let (width, requested_hidden) = if label == "taskbar" { (p.width, p.hidden) }
            else { (if state.width == 0 { p.width } else { state.width }, state.hidden) };
    let hidden = crate::platform::dock_placement_available() && requested_hidden
        && !crate::popup::is_for_dock(app, &label);
    let rect = geometry::dock_rect(
        crate::monitor_area(&monitor),
        monitor.scale_factor(),
        p.top,
        p.height,
        hidden,
        width,
    );
    // GTK/WM can constrain a cross-monitor move using the old wide allocation.
    // Once the requested size is acknowledged, correct position once. A newer
    // apply replaces this target; no timer or unbounded configure loop is used.
    let width_changes = window.outer_size().map_err(|e| e.to_string())?.width != rect.width;
    let placement_available = crate::platform::dock_placement_available();
    {
        let layout = app.state::<LayoutState>();
        let mut prefs = layout.0.lock().map_err(|e| e.to_string())?;
        let pending = (width_changes && placement_available).then_some(rect);
        if label == "taskbar" { prefs.pending_position = pending; }
        else { prefs.docks.entry(label.clone()).or_default().pending = pending; }
    }
    window
        .set_min_size(Some(PhysicalSize::new(1, 1)))
        .map_err(|e| e.to_string())?;
    window
        .set_size(PhysicalSize::new(rect.width, rect.height))
        .map_err(|e| e.to_string())?;
    if placement_available {
        window.set_position(PhysicalPosition::new(rect.x, rect.y)).map_err(|e| e.to_string())?;
    }
    if p.enabled && (created || !window.is_visible().unwrap_or(false)) { window.show().map_err(|e| e.to_string())?; }
    else if !p.enabled { window.hide().map_err(|e| e.to_string())?; }
    }
    Ok(true)
}
pub fn settle_size(app: &AppHandle, label: &str, size: &PhysicalSize<u32>) -> Result<(), String> {
    if crate::popup::is_active(app, "dock-context-menu") || crate::popup::is_active(app, "calendar-flyout") { return Ok(()); }
    let target = {
        let state = app.state::<LayoutState>();
        let mut p = state.0.lock().map_err(|e| e.to_string())?;
        let pending = if label == "taskbar" { &mut p.pending_position } else { &mut p.docks.entry(label.into()).or_default().pending };
        if !pending.is_some_and(|rect| rect.width == size.width && rect.height == size.height) { return Ok(()); }
        pending.take().unwrap()
    };
    let window = dock(app, Some(label))?;
    let position = window.outer_position().map_err(|e| e.to_string())?;
    if position.x != target.x || position.y != target.y {
        window.set_position(PhysicalPosition::new(target.x, target.y)).map_err(|e| e.to_string())?;
    }
    Ok(())
}
#[tauri::command]
pub fn set_dock_content_width(app: AppHandle, width: u32, source_dock: Option<String>) -> Result<bool, String> {
    let window = dock(&app, source_dock.as_deref())?;
    {
        let layout = app.state::<LayoutState>();
        let mut p = layout.0.lock().map_err(|e| e.to_string())?;
        if window.label() == "taskbar" { p.width = width.clamp(220, 6000); }
        else { p.docks.entry(window.label().into()).or_default().width = width.clamp(220, 6000); }
    }
    // Keep the popup anchored until the interaction ends.
    if crate::popup::is_active(&app, "dock-context-menu")
        || crate::popup::is_active(&app, "calendar-flyout")
    {
        return Ok(false);
    }
    apply(&app)
}
#[tauri::command]
pub fn is_pointer_over_dock(app: AppHandle, source_dock: Option<String>) -> Result<bool, String> {
    let _trace = crate::diagnostics::command("is_pointer_over_dock");
    if std::env::var("XDG_SESSION_TYPE").as_deref() != Ok("x11") {
        return Err("Global pointer position requires X11".into());
    }
    let dock = dock(&app, source_dock.as_deref())?;
    let pointer = dock.cursor_position().map_err(|e| e.to_string())?;
    let position = dock.outer_position().map_err(|e| e.to_string())?;
    let size = dock.outer_size().map_err(|e| e.to_string())?;
    Ok(geometry::Rect { x: position.x, y: position.y, width: size.width, height: size.height }
        .contains(pointer.x.floor() as i32, pointer.y.floor() as i32))
}
#[tauri::command]
pub fn set_taskbar_autohide_state(app: AppHandle, hidden: bool, source_dock: Option<String>) -> Result<bool, String> {
    if !crate::platform::dock_placement_available() {
        return if hidden { Err("dock_autohide_unverified".into()) } else { Ok(false) };
    }
    let window = dock(&app, source_dock.as_deref())?;
    {
        let layout = app.state::<LayoutState>();
        let mut p = layout.0.lock().map_err(|e| e.to_string())?;
        if window.label() == "taskbar" { p.hidden = hidden; }
        else { p.docks.entry(window.label().into()).or_default().hidden = hidden; }
    }
    apply(&app)
}
pub fn watch(app: &AppHandle) {
    stop_watching();
    let app = app.clone();
    let mut previous = String::new();
    // Monitor APIs dispatch to GTK. Poll them on that context instead of a
    // detached worker that can wait on a main thread already shutting down.
    let source = gio::glib::timeout_add_local(std::time::Duration::from_secs(2), move || {
        let Some(window) = app.get_webview_window("taskbar") else {
            return gio::glib::ControlFlow::Continue;
        };
        if let Ok(monitors) = window.available_monitors() {
            let signature = format!("{monitors:?}");
            if signature != previous {
                if !previous.is_empty() {
                    let _ = crate::popup::hide(&app, "dock-context-menu", None);
                    let _ = crate::popup::hide(&app, "calendar-flyout", None);
                    let _ = apply(&app);
                    let _ = app.emit("deskmorph:platform-changed", ());
                }
                previous = signature;
            }
        }
        gio::glib::ControlFlow::Continue
    });
    TOPOLOGY_WATCH.with(|watch| *watch.borrow_mut() = Some(source));
}
pub fn stop_watching() {
    TOPOLOGY_WATCH.with(|watch| {
        if let Some(source) = watch.borrow_mut().take() {
            source.remove();
        }
    });
}
