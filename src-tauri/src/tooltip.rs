use std::sync::Mutex;
use gtk::prelude::*;
use tauri::{AppHandle, Emitter, Manager, PhysicalPosition, PhysicalSize};
#[derive(Default)]
pub struct TooltipState(pub Mutex<u64>);
pub fn install(app: &AppHandle) -> Result<(), String> {
    let window = app.get_webview_window("dock-tooltip").ok_or("Không tìm thấy tooltip")?;
    let native = window.gtk_window().map_err(|e| e.to_string())?;
    native.set_accept_focus(false);
    native.set_focus_on_map(false);
    // Tao's set_ignore_cursor_events unwraps the GDK window, which does not
    // exist before first map (or after a queued hide). Apply on GTK map instead.
    native.connect_map(|widget| {
        if let Some(native) = widget.window() {
            native.input_shape_combine_region(&gtk::cairo::Region::create(), 0, 0);
        }
    });
    Ok(())
}
#[tauri::command]
pub fn set_dock_tooltip(app: AppHandle, revision: u64, text: Option<String>, anchor: Option<i32>) -> Result<(), String> {
    let state = app.state::<TooltipState>();
    let mut current = state.0.lock().map_err(|e| e.to_string())?;
    if revision < *current { return Ok(()); }
    *current = revision;
    let window = app.get_webview_window("dock-tooltip").ok_or("Không tìm thấy tooltip")?;
    if text.as_ref().is_none_or(|text| text.is_empty()) || crate::popup::is_active(&app, "dock-context-menu") || crate::popup::is_active(&app, "calendar-flyout") {
        return window.hide().map_err(|e| e.to_string());
    }
    let dock = app.get_webview_window("taskbar").ok_or("Không tìm thấy Dock")?;
    if !dock.is_visible().unwrap_or(false) { return Ok(()); }
    let monitor = dock.current_monitor().map_err(|e| e.to_string())?.ok_or("Không tìm thấy màn hình")?;
    let pos = dock.outer_position().map_err(|e| e.to_string())?;
    let size = dock.outer_size().map_err(|e| e.to_string())?;
    let area = crate::monitor_area(&monitor);
    let dock_rect = crate::geometry::Rect { x:pos.x, y:pos.y, width:size.width, height:size.height };
    let anchor = crate::geometry::anchor_x(dock_rect, anchor.unwrap_or(0), dock.scale_factor().map_err(|e| e.to_string())?);
    let rect = crate::geometry::popup_rect(area, dock_rect, monitor.scale_factor(), anchor, 250, 44, pos.y < area.y + area.height as i32 / 2);
    // Keep the small tooltip below WebKitGTK's natural height. Its undecorated
    // window is resizable in config so GTK honors resize rather than natural size;
    // the empty input region prevents interactive resizing.
    window.set_min_size(Some(PhysicalSize::new(1, 1))).map_err(|e| e.to_string())?;
    window.set_size(PhysicalSize::new(rect.width, rect.height)).map_err(|e| e.to_string())?;
    window.set_position(PhysicalPosition::new(rect.x, rect.y)).map_err(|e| e.to_string())?;
    window.emit("deskmorph:tooltip", text.unwrap().chars().take(200).collect::<String>()).map_err(|e| e.to_string())?;
    window.show().map_err(|e| e.to_string())
}
