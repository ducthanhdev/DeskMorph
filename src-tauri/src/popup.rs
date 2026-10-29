//! One popup at a time. A generation prevents old outside-click watchers closing newer popups.
use crate::window_manager::x11;
use std::sync::Mutex;
use gtk::prelude::*;
use tauri::{AppHandle, Emitter, Manager, PhysicalPosition, PhysicalSize};
use crate::geometry::{self, Rect};

#[repr(C)]
#[derive(Clone, Copy)]
struct GenericCookie {
    kind: std::os::raw::c_int,
    serial: std::os::raw::c_ulong,
    sent: std::os::raw::c_int,
    display: *mut std::ffi::c_void,
    extension: std::os::raw::c_int,
    event_type: std::os::raw::c_int,
    cookie: std::os::raw::c_uint,
    data: *mut std::ffi::c_void,
}
#[repr(C)]
union PointerEvent { kind: std::os::raw::c_int, cookie: GenericCookie, pad: [std::os::raw::c_long; 24] }
#[repr(C)]
struct InputMask { device: std::os::raw::c_int, length: std::os::raw::c_int, mask: *mut u8 }
#[link(name = "X11")]
extern "C" {
    fn XQueryExtension(display: *mut std::ffi::c_void, name: *const std::os::raw::c_char, opcode: *mut i32, event: *mut i32, error: *mut i32) -> i32;
    fn XPending(display: *mut std::ffi::c_void) -> i32;
    fn XNextEvent(display: *mut std::ffi::c_void, event: *mut PointerEvent) -> i32;
    fn XGetEventData(display: *mut std::ffi::c_void, cookie: *mut GenericCookie) -> i32;
    fn XFreeEventData(display: *mut std::ffi::c_void, cookie: *mut GenericCookie);
}
#[link(name = "Xi")]
extern "C" {
    fn XIQueryVersion(display: *mut std::ffi::c_void, major: *mut i32, minor: *mut i32) -> i32;
    fn XISelectEvents(display: *mut std::ffi::c_void, window: std::os::raw::c_ulong, masks: *mut InputMask, count: i32) -> i32;
}

unsafe fn raw_buttons(display: *mut std::ffi::c_void, root: std::os::raw::c_ulong) -> Option<i32> {
    let (mut opcode, mut event, mut error) = (0, 0, 0);
    if XQueryExtension(display, b"XInputExtension\0".as_ptr().cast(), &mut opcode, &mut event, &mut error) == 0 { return None; }
    let (mut major, mut minor) = (2, 0);
    if XIQueryVersion(display, &mut major, &mut minor) != 0 || major < 2 { return None; }
    // XIAllMasterDevices, XI_RawButtonPress. Events remain queued even when a
    // complete press/release occurs between watcher iterations.
    let mut bits = [0u8, 1 << 7];
    let mut mask = InputMask { device: 1, length: bits.len() as i32, mask: bits.as_mut_ptr() };
    if XISelectEvents(display, root, &mut mask, 1) != 0 { return None; }
    x11::XFlush(display);
    Some(opcode)
}

#[derive(Default)]
pub struct PopupState(pub Mutex<Coordinator>);
#[derive(Default)]
pub struct Coordinator { generation: u64, active: Option<(&'static str, Rect)>, audio: bool, dismiss_on_blur: bool }

fn hidden_events(app: &AppHandle, label: &str, generation: u64) {
    let event = if label == "calendar-flyout" { "deskmorph:calendar-visibility" } else { "deskmorph:context-menu-visibility" };
    let _ = app.emit(event, false);
    if label == "dock-context-menu" {
        let _ = app.emit("deskmorph:context-visibility-generation", serde_json::json!({"generation": generation, "visible": false}));
    }
    let _ = app.emit("deskmorph:popup-visible", false);
}
#[track_caller]
pub fn hide(app: &AppHandle, label: &str, generation: Option<u64>) -> Result<bool, String> {
    let state = app.state::<PopupState>();
    let mut c = state.0.lock().map_err(|e| e.to_string())?;
    if generation.is_some_and(|g| g != c.generation) { return Ok(false); }
    let hidden = c.active.is_some_and(|(active, _)| active == label);
    if hidden {
        #[cfg(debug_assertions)]
        if std::env::var_os("DESKMORPH_TRACE_POPUP_DISMISS").is_some() {
            eprintln!("deskmorph-popup-dismiss label={label} generation={} caller={}", c.generation, std::panic::Location::caller());
        }
        if let Some(window) = app.get_webview_window(label) { window.hide().map_err(|e| e.to_string())?; }
        c.active = None;
        hidden_events(app, label, c.generation);
        c.generation = c.generation.wrapping_add(1);
    }
    drop(c);
    // Content width can change while a popup anchors to the old Dock rect.
    // Apply that deferred layout when the interaction ends, outside the lock:
    // layout::apply checks the coordinator again for popup/auto-hide state.
    if hidden { crate::layout::apply(app)?; }
    Ok(true)
}
pub fn active_generation(app: &AppHandle, label: &str) -> Option<u64> {
    app.state::<PopupState>().0.lock().ok().and_then(|c| c.active.filter(|(active, _)| *active == label).map(|_| c.generation))
}
pub fn is_audio_active(app: &AppHandle) -> bool {
    app.state::<PopupState>().0.lock().map(|c| c.audio && c.active.is_some()).unwrap_or(false)
}
pub fn is_active(app: &AppHandle, label: &str) -> bool {
    app.state::<PopupState>().0.lock().map(|c| c.active.is_some_and(|(active, _)| active == label)).unwrap_or(false)
}
pub fn dismiss_on_blur(app: &AppHandle, label: &str) -> bool {
    app.state::<PopupState>().0.lock().map(|c| c.dismiss_on_blur && c.active.is_some_and(|(active, _)| active == label)).unwrap_or(false)
}
/// Use the timestamp of the native shortcut event so the WM can distinguish
/// explicit keyboard activation from a background application's focus request.
pub fn focus_at(app: &AppHandle, label: &'static str, timestamp: u32) -> Result<(), String> {
    let Some(generation) = active_generation(app, label) else { return Ok(()); };
    let handle = app.clone();
    app.get_webview_window(label).ok_or("Không tìm thấy popup")?.with_webview(move |platform| {
        let view = platform.inner();
        gio::glib::idle_add_local_once(move || {
            if active_generation(&handle, label) != Some(generation) { return; }
            if let Some(top) = view.toplevel().and_then(|window| window.downcast::<gtk::Window>().ok()) {
                top.present_with_time(timestamp);
                view.grab_focus();
            }
        });
    }).map_err(|e| e.to_string())
}
/// Debug-only timing control for exercising native focus races. No delay in release.
fn after_mapping(callback: impl FnOnce() + 'static) {
    #[cfg(debug_assertions)]
    let delay = std::env::var("DESKMORPH_TEST_POPUP_FOCUS_DELAY_MS").ok()
        .and_then(|value| value.parse::<u64>().ok()).filter(|value| *value <= 1000).unwrap_or(0);
    #[cfg(not(debug_assertions))]
    let delay = 0;
    if delay == 0 { gio::glib::idle_add_local_once(callback); }
    else { gio::glib::timeout_add_local_once(std::time::Duration::from_millis(delay), callback); }
}
pub fn show(app: &AppHandle, label: &'static str, anchor: i32, width: u32, height: u32, data: Option<serde_json::Value>) -> Result<bool, String> {
    let dock = app.get_webview_window("taskbar").ok_or("Không tìm thấy Dock")?;
    if !dock.is_visible().map_err(|e| e.to_string())? { return Err("Dock đang tắt".into()); }
    let monitor = dock.current_monitor().map_err(|e| e.to_string())?.ok_or("Không tìm thấy màn hình")?;
    let scale = monitor.scale_factor();
    let area = super::monitor_area(&monitor);
    let position = dock.outer_position().map_err(|e| e.to_string())?;
    let size = dock.outer_size().map_err(|e| e.to_string())?;
    let dock_rect = Rect { x: position.x, y: position.y, width: size.width, height: size.height };
    let top = position.y < area.y + area.height as i32 / 2;
    let anchor = geometry::anchor_x(dock_rect, anchor, dock.scale_factor().map_err(|e| e.to_string())?);
    let rect = geometry::popup_rect(area, dock_rect, scale, anchor, width, height, top);
    #[cfg(debug_assertions)]
    if std::env::var_os("DESKMORPH_TRACE_POPUP_DISMISS").is_some() {
        eprintln!("deskmorph-popup-placement area={area:?} dock={dock_rect:?} popup={rect:?}");
    }
    present(app, label, Some(rect), data, None)
}
/// A desktop-managed launcher is an ordinary toplevel on Wayland. Its position
/// belongs to the compositor; it does not require Dock placement or an anchor.
pub fn show_unanchored_launcher(app: &AppHandle, token: Option<&str>) -> Result<bool, String> {
    present(app, "dock-context-menu", None, Some(serde_json::json!({"mode":"launcher","appName":"Ứng dụng"})), token)
}
fn present(app: &AppHandle, label: &'static str, placement: Option<Rect>, data: Option<serde_json::Value>, token: Option<&str>) -> Result<bool, String> {
    let state = app.state::<PopupState>();
    let mut c = state.0.lock().map_err(|e| e.to_string())?;
    if let Some(tooltip) = app.get_webview_window("dock-tooltip") { let _ = tooltip.hide(); }
    if let Some((old, _)) = c.active.take() {
        if let Some(window) = app.get_webview_window(old) { window.hide().map_err(|e| e.to_string())?; }
        hidden_events(app, old, c.generation);
    }
    c.generation = c.generation.wrapping_add(1);
    let generation = c.generation;
    let window = app.get_webview_window(label).ok_or("Không tìm thấy popup")?;
    if label == "dock-context-menu" {
        // Reused by anchored popups and the ordinary CLI launcher. Reset all
        // shell hints on every open so one mode cannot leak into the next.
        let gtk = window.gtk_window().map_err(|e| e.to_string())?;
        gtk.set_decorated(placement.is_none());
        gtk.set_skip_taskbar_hint(placement.is_some());
        gtk.set_keep_above(placement.is_some());
        window.set_title(if placement.is_some() { "DeskMorph Context Menu" } else { "DeskMorph Launcher" }).map_err(|e| e.to_string())?;
    }
    window.set_min_size(Some(PhysicalSize::new(1, 1))).map_err(|e| e.to_string())?;
    let rect = if let Some(rect) = placement {
        window.set_size(PhysicalSize::new(rect.width, rect.height)).map_err(|e| e.to_string())?;
        window.set_position(PhysicalPosition::new(rect.x, rect.y)).map_err(|e| e.to_string())?;
        rect
    } else {
        window.set_size(tauri::LogicalSize::new(500., 580.)).map_err(|e| e.to_string())?;
        Rect { x: 0, y: 0, width: 500, height: 580 }
    };
    if let Some(token) = token { window.gtk_window().map_err(|e| e.to_string())?.set_startup_id(token); }
    c.audio = data.as_ref().is_some_and(|data| data["mode"] == "audio");
    // A compositor may deny activation to a command without an input token.
    // Keep the ordinary launcher available for explicit user activation.
    c.dismiss_on_blur = placement.is_some();
    if let Some(mut data) = data {
        data["popupGeneration"] = generation.into();
        window.emit("deskmorph:context-menu-data", data).map_err(|e| e.to_string())?;
    }
    window.show().map_err(|e| e.to_string())?;
    window.set_focus().map_err(|e| e.to_string())?;
    c.active = Some((label, rect));
    let event = if label == "calendar-flyout" { "deskmorph:calendar-visibility" } else { "deskmorph:context-menu-visibility" };
    app.emit(event, true).map_err(|e| e.to_string())?;
    if label == "dock-context-menu" {
        app.emit("deskmorph:context-visibility-generation", serde_json::json!({"generation": generation, "visible": true})).map_err(|e| e.to_string())?;
    }
    app.emit("deskmorph:popup-visible", true).map_err(|e| e.to_string())?;
    drop(c);
    let handle = app.clone();
    let focus_window = window.clone();
    window.with_webview(move |platform| {
        let view = platform.inner();
        // Native activation belongs to the opening gesture above. A deferred
        // content callback must never present a toplevel over a newer user choice.
        after_mapping(move || {
            let current = active_generation(&handle, label) == Some(generation);
            let focused = focus_window.is_focused().unwrap_or(false);
            // A remapped X11 toplevel can retain the WM's pre-topology
            // position despite a move queued while hidden. Correct once after
            // mapping, guarded against a replaced or dismissed popup.
            if current {
                if let Some(rect) = placement {
                    let _ = focus_window.set_position(PhysicalPosition::new(rect.x, rect.y));
                }
            }
            #[cfg(debug_assertions)]
            if std::env::var_os("DESKMORPH_TEST_POPUP_FOCUS_DELAY_MS").is_some() {
                eprintln!("deskmorph-popup-content-focus generation={generation} active={current} focused={focused}");
            }
            if !current || !focused { return; }
            view.grab_focus();
        });
    }).map_err(|e| e.to_string())?;
    if placement.is_some() { watch_outside(app.clone(), label, generation, rect); }
    Ok(true)
}
/// Handle dismissal at the native toplevel as well as in the web document.
/// WebKit can retain DOM focus across a hidden/remapped view while its DOM
/// key listener no longer receives Escape after rapid popup replacement.
pub fn install_keyboard(app: &AppHandle) -> Result<(), String> {
    for label in ["main", "taskbar", "dock-context-menu", "calendar-flyout"] {
        let window = app.get_webview_window(label).ok_or("Không tìm thấy popup")?;
        let handle = app.clone();
        window.gtk_window().map_err(|e| e.to_string())?.connect_key_press_event(move |_, event| {
            if event.keyval() == gtk::gdk::keys::constants::Escape {
                let active = handle.state::<PopupState>().0.lock().ok()
                    .and_then(|c| c.active.map(|(label, _)| (label, c.generation)));
                if let Some((active, generation)) = active {
                    let _ = hide(&handle, active, Some(generation));
                    return gio::glib::Propagation::Stop;
                }
            }
            gio::glib::Propagation::Proceed
        });
    }
    Ok(())
}
fn watch_outside(app: AppHandle, label: &'static str, generation: u64, rect: Rect) {
    // X11 only; focus/escape still work when no pointer connection is available.
    if std::env::var("XDG_SESSION_TYPE").as_deref() != Ok("x11") { return; }
    std::thread::spawn(move || unsafe {
        let display = x11::XOpenDisplay(std::ptr::null());
        if display.is_null() { return; }
        let root = x11::XDefaultRootWindow(display);
        let raw_opcode = raw_buttons(display, root);
        let mut armed = false;
        loop {
            let current = app.state::<PopupState>().0.lock().map(|c| c.generation == generation && c.active.is_some()).unwrap_or(false);
            if !current { break; }
            let mut raw_pressed = false;
            while XPending(display) > 0 {
                let mut event: PointerEvent = std::mem::zeroed();
                XNextEvent(display, &mut event);
                if event.kind == 35 {
                    if raw_opcode == Some(event.cookie.extension) && event.cookie.event_type == 15 { raw_pressed = true; }
                    if XGetEventData(display, &mut event.cookie) != 0 { XFreeEventData(display, &mut event.cookie); }
                }
            }
            let (mut root_return, mut child_return, mut root_x, mut root_y, mut win_x, mut win_y, mut mask) = (0, 0, 0, 0, 0, 0, 0);
            let ok = x11::XQueryPointer(display, root, &mut root_return, &mut child_return, &mut root_x, &mut root_y, &mut win_x, &mut win_y, &mut mask);
            if ok != 0 {
                let pressed = mask & 0x700 != 0;
                if !pressed { armed = true; }
                if armed && (raw_pressed || (raw_opcode.is_none() && pressed)) && !rect.contains(root_x, root_y) {
                    let _ = hide(&app, label, Some(generation));
                    break;
                }
            }
            std::thread::sleep(std::time::Duration::from_millis(40));
        }
        x11::XCloseDisplay(display);
    });
}
