use crate::geometry;
use std::sync::Mutex;
use tauri::{AppHandle, Emitter, Manager, PhysicalPosition, PhysicalSize};
#[derive(Clone)]
pub struct Preferences {
    monitor: Option<String>,
    width: u32,
    height: u32,
    top: bool,
    hidden: bool,
    pending_position: Option<geometry::Rect>,
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
        }
    }
}
#[derive(Default)]
pub struct LayoutState(pub Mutex<Preferences>);
thread_local! {
    static TOPOLOGY_WATCH: std::cell::RefCell<Option<gio::glib::SourceId>> = const { std::cell::RefCell::new(None) };
}
pub fn configure(app: &AppHandle, config: &serde_json::Value) -> Result<(), String> {
    let state = app.state::<LayoutState>();
    let mut p = state.0.lock().map_err(|e| e.to_string())?;
    p.monitor = config["monitor"].as_str().map(String::from);
    p.height = config["height"].as_u64().unwrap_or(52) as u32;
    p.top = config["position"] == "top";
    if config["autoHide"] != true {
        p.hidden = false;
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
    let preferred = p
        .monitor
        .as_ref()
        .and_then(|name| monitors.iter().find(|m| m.name() == Some(name)))
        .cloned();
    let monitor = preferred
        .or(window.primary_monitor().map_err(|e| e.to_string())?)
        .or(monitors.into_iter().next())
        .ok_or("Không tìm thấy màn hình")?;
    let hidden = crate::platform::dock_placement_available() && p.hidden
        && !crate::popup::is_active(app, "dock-context-menu")
        && !crate::popup::is_active(app, "calendar-flyout");
    let rect = geometry::dock_rect(
        crate::monitor_area(&monitor),
        monitor.scale_factor(),
        p.top,
        p.height,
        hidden,
        p.width,
    );
    // GTK/WM can constrain a cross-monitor move using the old wide allocation.
    // Once the requested size is acknowledged, correct position once. A newer
    // apply replaces this target; no timer or unbounded configure loop is used.
    let width_changes = window.outer_size().map_err(|e| e.to_string())?.width != rect.width;
    app.state::<LayoutState>().0.lock().map_err(|e| e.to_string())?.pending_position = width_changes.then_some(rect);
    window
        .set_min_size(Some(PhysicalSize::new(1, 1)))
        .map_err(|e| e.to_string())?;
    window
        .set_size(PhysicalSize::new(rect.width, rect.height))
        .map_err(|e| e.to_string())?;
    window
        .set_position(PhysicalPosition::new(rect.x, rect.y))
        .map_err(|e| e.to_string())?;
    Ok(true)
}
pub fn settle_size(app: &AppHandle, size: &PhysicalSize<u32>) -> Result<(), String> {
    if crate::popup::is_active(app, "dock-context-menu") || crate::popup::is_active(app, "calendar-flyout") { return Ok(()); }
    let target = {
        let state = app.state::<LayoutState>();
        let mut p = state.0.lock().map_err(|e| e.to_string())?;
        if !p.pending_position.is_some_and(|rect| rect.width == size.width && rect.height == size.height) { return Ok(()); }
        p.pending_position.take().unwrap()
    };
    let window = app.get_webview_window("taskbar").ok_or("Không tìm thấy Dock")?;
    let position = window.outer_position().map_err(|e| e.to_string())?;
    if position.x != target.x || position.y != target.y {
        window.set_position(PhysicalPosition::new(target.x, target.y)).map_err(|e| e.to_string())?;
    }
    Ok(())
}
#[tauri::command]
pub fn set_dock_content_width(app: AppHandle, width: u32) -> Result<bool, String> {
    app.state::<LayoutState>()
        .0
        .lock()
        .map_err(|e| e.to_string())?
        .width = width.clamp(220, 6000);
    // Keep the popup anchored until the interaction ends.
    if crate::popup::is_active(&app, "dock-context-menu")
        || crate::popup::is_active(&app, "calendar-flyout")
    {
        return Ok(false);
    }
    apply(&app)
}
#[tauri::command]
pub fn is_pointer_over_dock(app: AppHandle) -> Result<bool, String> {
    let _trace = crate::diagnostics::command("is_pointer_over_dock");
    if std::env::var("XDG_SESSION_TYPE").as_deref() != Ok("x11") {
        return Err("Global pointer position requires X11".into());
    }
    let dock = app.get_webview_window("taskbar").ok_or("Không tìm thấy Dock")?;
    let pointer = dock.cursor_position().map_err(|e| e.to_string())?;
    let position = dock.outer_position().map_err(|e| e.to_string())?;
    let size = dock.outer_size().map_err(|e| e.to_string())?;
    Ok(geometry::Rect { x: position.x, y: position.y, width: size.width, height: size.height }
        .contains(pointer.x.floor() as i32, pointer.y.floor() as i32))
}
#[tauri::command]
pub fn set_taskbar_autohide_state(app: AppHandle, hidden: bool) -> Result<bool, String> {
    if !crate::platform::dock_placement_available() {
        return if hidden { Err("dock_autohide_unverified".into()) } else { Ok(false) };
    }
    app.state::<LayoutState>()
        .0
        .lock()
        .map_err(|e| e.to_string())?
        .hidden = hidden;
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
