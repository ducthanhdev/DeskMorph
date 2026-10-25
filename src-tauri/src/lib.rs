use serde::{Deserialize, Serialize};
use std::fs;
use std::os::raw::{c_char, c_int, c_long, c_uint, c_ulong, c_void};
use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;
use sysinfo::System;
use tauri::{AppHandle, Emitter, Manager, PhysicalPosition, PhysicalSize};

static MENU_IS_OPEN: AtomicBool = AtomicBool::new(false);

#[repr(C)]
#[derive(Copy, Clone)]
struct XClientMessageEvent {
    type_: c_int,
    serial: c_ulong,
    send_event: c_int,
    display: *mut c_void,
    window: c_ulong,
    message_type: c_ulong,
    format: c_int,
    data: [c_long; 5],
}

#[repr(C)]
#[derive(Copy, Clone)]
union XEvent {
    type_: c_int,
    xclient: XClientMessageEvent,
    pad: [c_long; 24],
}

#[link(name = "X11")]
extern "C" {
    fn XOpenDisplay(display_name: *const c_char) -> *mut c_void;
    fn XDefaultRootWindow(display: *mut c_void) -> c_ulong;
    fn XInternAtom(
        display: *mut c_void,
        atom_name: *const c_char,
        only_if_exists: c_int,
    ) -> c_ulong;
    fn XSendEvent(
        display: *mut c_void,
        w: c_ulong,
        propagate: c_int,
        event_mask: c_long,
        event_send: *mut XEvent,
    ) -> c_int;
    fn XKillClient(display: *mut c_void, resource: c_ulong) -> c_int;
    fn XQueryPointer(
        display: *mut c_void,
        w: c_ulong,
        root_return: *mut c_ulong,
        child_return: *mut c_ulong,
        root_x_return: *mut c_int,
        root_y_return: *mut c_int,
        win_x_return: *mut c_int,
        win_y_return: *mut c_int,
        mask_return: *mut c_uint,
    ) -> c_int;
    fn XFlush(display: *mut c_void) -> c_int;
    fn XCloseDisplay(display: *mut c_void) -> c_int;
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct SystemStats {
    pub cpu_usage: f32,
    pub ram_used_mb: u64,
    pub ram_total_mb: u64,
    pub ram_percent: f32,
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct WallpaperInfo {
    pub path: String,
    pub filename: String,
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct OpenWindow {
    pub id: String,
    pub class_name: String,
    pub title: String,
    pub is_active: bool,
}

pub struct AppState {
    pub sys: Mutex<System>,
}

#[tauri::command]
fn get_system_stats(state: tauri::State<AppState>) -> Result<SystemStats, String> {
    let mut sys = state.sys.lock().map_err(|e| e.to_string())?;
    sys.refresh_cpu_all();
    sys.refresh_memory();

    let cpus = sys.cpus();
    let cpu_usage: f32 = if !cpus.is_empty() {
        cpus.iter().map(|c| c.cpu_usage()).sum::<f32>() / (cpus.len() as f32)
    } else {
        0.0
    };

    let total_ram = sys.total_memory() / (1024 * 1024);
    let used_ram = sys.used_memory() / (1024 * 1024);
    let ram_percent = if total_ram > 0 {
        (used_ram as f32 / total_ram as f32) * 100.0
    } else {
        0.0
    };

    Ok(SystemStats {
        cpu_usage: (cpu_usage * 10.0).round() / 10.0,
        ram_used_mb: used_ram,
        ram_total_mb: total_ram,
        ram_percent: (ram_percent * 10.0).round() / 10.0,
    })
}

#[tauri::command]
fn get_wallpapers(folder: Option<String>) -> Result<Vec<WallpaperInfo>, String> {
    let search_dirs = match folder {
        Some(f) if !f.trim().is_empty() => vec![PathBuf::from(f)],
        _ => {
            let mut dirs = vec![
                PathBuf::from("/usr/share/backgrounds"),
                PathBuf::from("/usr/share/backgrounds/pop"),
            ];
            if let Ok(home) = std::env::var("HOME") {
                dirs.push(PathBuf::from(&home).join("Pictures"));
                dirs.push(PathBuf::from(&home).join("Pictures/Wallpapers"));
            }
            dirs
        }
    };

    let mut result = Vec::new();
    let valid_exts = ["jpg", "jpeg", "png", "webp", "bmp"];

    for dir in search_dirs {
        if !dir.exists() {
            continue;
        }
        if let Ok(entries) = fs::read_dir(dir) {
            for entry in entries.flatten() {
                let p = entry.path();
                if p.is_file() {
                    if let Some(ext) = p.extension().and_then(|s| s.to_str()) {
                        if valid_exts.contains(&ext.to_lowercase().as_str()) {
                            let filename = p
                                .file_name()
                                .unwrap_or_default()
                                .to_string_lossy()
                                .to_string();
                            result.push(WallpaperInfo {
                                path: p.to_string_lossy().to_string(),
                                filename,
                            });
                        }
                    }
                }
            }
        }
    }

    result.dedup_by(|a, b| a.path == b.path);
    Ok(result)
}

#[tauri::command]
fn get_current_wallpaper() -> Result<String, String> {
    let output = Command::new("gsettings")
        .args(["get", "org.gnome.desktop.background", "picture-uri-dark"])
        .output()
        .map_err(|e| e.to_string())?;

    let out_str = String::from_utf8_lossy(&output.stdout)
        .trim()
        .trim_matches('\'')
        .to_string();
    let cleaned = out_str
        .strip_prefix("file://")
        .unwrap_or(&out_str)
        .to_string();
    Ok(cleaned)
}

#[tauri::command]
fn set_wallpaper(path: String) -> Result<bool, String> {
    let uri = if path.starts_with("file://") {
        path.clone()
    } else {
        format!("file://{}", path)
    };

    let status_dark = Command::new("gsettings")
        .args([
            "set",
            "org.gnome.desktop.background",
            "picture-uri-dark",
            &uri,
        ])
        .status()
        .map_err(|e| e.to_string())?;

    let _ = Command::new("gsettings")
        .args(["set", "org.gnome.desktop.background", "picture-uri", &uri])
        .status();

    Ok(status_dark.success())
}

#[tauri::command]
fn toggle_taskbar(app: AppHandle, visible: bool) -> Result<bool, String> {
    if let Some(window) = app.get_webview_window("taskbar") {
        if visible {
            let _ = reposition_taskbar(app.clone(), "bottom".to_string(), Some(54));
            window.show().map_err(|e| e.to_string())?;
            let _ = window.set_always_on_top(true);
        } else {
            window.hide().map_err(|e| e.to_string())?;
        }
        Ok(visible)
    } else {
        Err("Taskbar window not found".to_string())
    }
}


#[tauri::command]
fn reposition_taskbar(
    app: AppHandle,
    position: String,
    height: Option<u32>,
) -> Result<bool, String> {
    if let Some(window) = app.get_webview_window("taskbar") {
        let _ = window.set_min_size(Some(PhysicalSize::new(100, 4)));
        if let Ok(Some(monitor)) = window.current_monitor() {
            let size = monitor.size();
            let screen_w = size.width as i32;
            let screen_h = size.height as i32;
            let bar_w = 1100.min(screen_w - 40);
            let bar_h = height.unwrap_or(54).clamp(40, 90) as i32;
            let x = (screen_w - bar_w) / 2;

            let y = if position == "top" {
                16
            } else {
                screen_h - bar_h - 16
            };

            let _ = window.set_size(PhysicalSize::new(bar_w as u32, bar_h as u32));
            let _ = window.set_position(PhysicalPosition::new(x, y));
        }
        Ok(true)
    } else {
        Err("Taskbar window not found".to_string())
    }
}

#[tauri::command]
fn set_taskbar_autohide_state(
    app: AppHandle,
    hidden: bool,
    height: Option<u32>,
    position: String,
) -> Result<bool, String> {
    if let Some(window) = app.get_webview_window("taskbar") {
        let _ = window.set_min_size(Some(PhysicalSize::new(100, 4)));
        if let Ok(Some(monitor)) = window.current_monitor() {
            let size = monitor.size();
            let screen_w = size.width as i32;
            let screen_h = size.height as i32;
            let bar_w = 1100.min(screen_w - 40);
            let bar_h = height.unwrap_or(54).clamp(40, 90) as i32;
            let x = (screen_w - bar_w) / 2;

            if hidden {
                let trigger_h = 4;
                let y = if position == "top" {
                    0
                } else {
                    screen_h - trigger_h
                };
                let _ = window.set_size(PhysicalSize::new(bar_w as u32, trigger_h as u32));
                let _ = window.set_position(PhysicalPosition::new(x, y));
            } else {
                let y = if position == "top" {
                    16
                } else {
                    screen_h - bar_h - 16
                };
                let _ = window.set_size(PhysicalSize::new(bar_w as u32, bar_h as u32));
                let _ = window.set_position(PhysicalPosition::new(x, y));
            }
        }
        Ok(true)
    } else {
        Err("Taskbar window not found".to_string())
    }
}

#[tauri::command]
fn show_dock_context_menu(
    app: AppHandle,
    icon_center_x: i32,
    menu_data: serde_json::Value,
) -> Result<bool, String> {
    let menu_window = app
        .get_webview_window("dock-context-menu")
        .ok_or_else(|| "dock-context-menu window not found".to_string())?;

    let (screen_w, screen_h) = if let Ok(Some(monitor)) = menu_window.current_monitor() {
        let size = monitor.size();
        (size.width as i32, size.height as i32)
    } else {
        (1920, 1080)
    };

    let bar_w = 1100.min(screen_w - 40);
    let (dock_x, dock_top) = if let Some(tb_win) = app.get_webview_window("taskbar") {
        if let Ok(pos) = tb_win.outer_position() {
            (pos.x, pos.y)
        } else {
            ((screen_w - bar_w) / 2, screen_h - 54 - 16)
        }
    } else {
        ((screen_w - bar_w) / 2, screen_h - 54 - 16)
    };

    let is_running = menu_data
        .get("isRunning")
        .and_then(|v| v.as_bool())
        .unwrap_or(false);

    let menu_w = 210u32;
    // Snug fit for menu content
    let menu_h = if is_running { 184u32 } else { 122u32 };

    let _ = menu_window.set_size(PhysicalSize::new(menu_w, menu_h));

    // Center menu horizontally on the icon X
    let target_x = (dock_x + icon_center_x - (menu_w as i32) / 2)
        .clamp(10, screen_w - (menu_w as i32) - 10);
    
    // Position menu with 14px comfortable floating gap above dock container
    let gap = 14i32;
    let is_top_dock = dock_top < screen_h / 2;
    let target_y = if is_top_dock {
        dock_top + 54 + gap
    } else {
        dock_top - (menu_h as i32) - gap
    };

    let _ = menu_window.set_position(PhysicalPosition::new(target_x, target_y));
    let _ = menu_window.emit("deskmorph:context-menu-data", menu_data);
    let _ = menu_window.show();
    let _ = menu_window.set_always_on_top(true);
    let _ = menu_window.set_focus();
    let _ = app.emit("deskmorph:context-menu-visibility", true);

    // Track outside clicks across the entire desktop using XQueryPointer
    MENU_IS_OPEN.store(true, Ordering::SeqCst);
    let app_handle = app.clone();
    std::thread::spawn(move || {
        unsafe {
            let display = XOpenDisplay(std::ptr::null());
            if display.is_null() {
                return;
            }
            let root = XDefaultRootWindow(display);
            let mut was_pressed = false;

            // 160ms grace period so releasing the right-click that spawned menu isn't treated as outside click
            std::thread::sleep(std::time::Duration::from_millis(160));

            while MENU_IS_OPEN.load(Ordering::SeqCst) {
                let mut root_return: c_ulong = 0;
                let mut child_return: c_ulong = 0;
                let mut root_x: c_int = 0;
                let mut root_y: c_int = 0;
                let mut win_x: c_int = 0;
                let mut win_y: c_int = 0;
                let mut mask: c_uint = 0;

                let ok = XQueryPointer(
                    display,
                    root,
                    &mut root_return,
                    &mut child_return,
                    &mut root_x,
                    &mut root_y,
                    &mut win_x,
                    &mut win_y,
                    &mut mask,
                );

                if ok != 0 {
                    // Check if mouse button 1 (left), 2 (middle), or 3 (right) is down
                    let is_pressed = (mask & 0x700) != 0;

                    if is_pressed && !was_pressed {
                        // Mouse down detected. Is it outside the menu rectangle?
                        let inside_menu = root_x >= (target_x - 3)
                            && root_x <= (target_x + (menu_w as i32) + 3)
                            && root_y >= (target_y - 3)
                            && root_y <= (target_y + (menu_h as i32) + 3);

                        if !inside_menu {
                            MENU_IS_OPEN.store(false, Ordering::SeqCst);
                            let _ = hide_dock_context_menu(app_handle.clone());
                            break;
                        }
                    }
                    was_pressed = is_pressed;
                }

                std::thread::sleep(std::time::Duration::from_millis(25));
            }

            XCloseDisplay(display);
        }
    });

    Ok(true)
}

#[tauri::command]
fn hide_dock_context_menu(app: AppHandle) -> Result<bool, String> {
    MENU_IS_OPEN.store(false, Ordering::SeqCst);
    if let Some(window) = app.get_webview_window("dock-context-menu") {
        let _ = window.hide();
        let _ = app.emit("deskmorph:context-menu-visibility", false);
    }
    Ok(true)
}

#[tauri::command]
fn set_taskbar_menu_expanded(
    _app: AppHandle,
    _expanded: bool,
    _dock_height: Option<u32>,
    _position: String,
) -> Result<bool, String> {
    // No-op: Taskbar window stays strictly at 54px without expanding,
    // eliminating any phantom window overlays or mutter resize issues!
    Ok(true)
}

fn get_best_executable_path() -> PathBuf {
    if let Ok(current) = std::env::current_exe() {
        if current.to_string_lossy().contains("/target/debug/") {
            let rel = current
                .parent()
                .and_then(|p| p.parent())
                .map(|p| p.join("release").join(current.file_name().unwrap_or_default()));
            if let Some(r) = rel {
                if r.exists() {
                    return r;
                }
            }
        }
        current
    } else {
        PathBuf::from("/home/ducthanhdev/Documents/Projects/Tool-private/src-tauri/target/release/deskmorph")
    }
}

#[tauri::command]
fn is_autostart_enabled() -> bool {
    if let Ok(home) = std::env::var("HOME") {
        let p = Path::new(&home).join(".config/autostart/deskmorph.desktop");
        p.exists()
    } else {
        false
    }
}

#[tauri::command]
fn set_autostart(enabled: bool) -> Result<bool, String> {
    let home = std::env::var("HOME").map_err(|e| e.to_string())?;
    let autostart_dir = Path::new(&home).join(".config/autostart");
    let desktop_file = autostart_dir.join("deskmorph.desktop");

    if enabled {
        let _ = fs::create_dir_all(&autostart_dir);
        let exe = get_best_executable_path();
        let content = format!(
            "[Desktop Entry]\nType=Application\nName=DeskMorph\nComment=DeskMorph Customization Studio & Taskbar\nExec=env WEBKIT_DISABLE_DMABUF_RENDERER=1 {}\nHidden=false\nNoDisplay=false\nX-GNOME-Autostart-enabled=true\nStartupNotify=false\nTerminal=false\n",
            exe.to_string_lossy()
        );
        fs::write(desktop_file, content).map_err(|e| e.to_string())?;
    } else if desktop_file.exists() {
        let _ = fs::remove_file(desktop_file);
    }

    Ok(enabled)
}

#[tauri::command]
fn install_app_icon() -> Result<bool, String> {
    let home = std::env::var("HOME").map_err(|e| e.to_string())?;
    let app_dir = Path::new(&home).join(".local/share/applications");
    let _ = fs::create_dir_all(&app_dir);
    let desktop_file = app_dir.join("deskmorph.desktop");

    let exe = get_best_executable_path();
    let content = format!(
        "[Desktop Entry]\nType=Application\nName=DeskMorph\nComment=DeskMorph Customization Studio & Taskbar\nExec=env WEBKIT_DISABLE_DMABUF_RENDERER=1 {}\nIcon=preferences-desktop-theme\nCategories=Utility;Settings;\nTerminal=false\nStartupNotify=false\n",
        exe.to_string_lossy()
    );
    fs::write(desktop_file, content).map_err(|e| e.to_string())?;
    Ok(true)
}

#[tauri::command]
fn get_open_windows() -> Result<Vec<OpenWindow>, String> {
    let active_id = Command::new("xprop")
        .args(["-root", "_NET_ACTIVE_WINDOW"])
        .output()
        .ok()
        .and_then(|out| {
            let s = String::from_utf8_lossy(&out.stdout);
            s.split('#').nth(1).map(|id| id.trim().to_lowercase())
        })
        .unwrap_or_default();

    let output = Command::new("xprop")
        .args(["-root", "_NET_CLIENT_LIST"])
        .output()
        .map_err(|e| e.to_string())?;

    let out_str = String::from_utf8_lossy(&output.stdout);
    let ids_part = match out_str.split('#').nth(1) {
        Some(p) => p.trim(),
        None => return Ok(Vec::new()),
    };

    let mut windows = Vec::new();
    for raw_id in ids_part.split(',') {
        let wid = raw_id.trim();
        if wid.is_empty() {
            continue;
        }

        if let Ok(info_out) = Command::new("xprop")
            .args([
                "-id",
                wid,
                "WM_CLASS",
                "_NET_WM_NAME",
                "WM_NAME",
                "_NET_WM_WINDOW_TYPE",
            ])
            .output()
        {
            let info = String::from_utf8_lossy(&info_out.stdout);

            if info.contains("_NET_WM_WINDOW_TYPE_DOCK")
                || info.contains("_NET_WM_WINDOW_TYPE_DESKTOP")
            {
                continue;
            }

            let mut class_name = String::from("App");
            if let Some(pos) = info.find("WM_CLASS(STRING) = ") {
                let line = info[pos + 19..].lines().next().unwrap_or_default();
                let parts: Vec<&str> = line.split(',').collect();
                if parts.len() >= 2 {
                    let c = parts[1].trim().trim_matches('"').trim();
                    if !c.is_empty() {
                        class_name = c.to_string();
                    }
                } else if !parts.is_empty() {
                    let c = parts[0].trim().trim_matches('"').trim();
                    if !c.is_empty() {
                        class_name = c.to_string();
                    }
                }
            }

            // Exclude taskbar window
            if class_name.eq_ignore_ascii_case("deskmorph") && info.contains("DeskMorph Taskbar") {
                continue;
            }

            let mut title = class_name.clone();
            if let Some(pos) = info.find("_NET_WM_NAME(UTF8_STRING) = \"") {
                let rest = &info[pos + 29..];
                if let Some(end) = rest.find('"') {
                    title = rest[..end].to_string();
                }
            } else if let Some(pos) = info.find("WM_NAME(UTF8_STRING) = \"") {
                let rest = &info[pos + 24..];
                if let Some(end) = rest.find('"') {
                    title = rest[..end].to_string();
                }
            }

            let is_active = !active_id.is_empty() && wid.to_lowercase().contains(&active_id);

            windows.push(OpenWindow {
                id: wid.to_string(),
                class_name,
                title,
                is_active,
            });
        }
    }

    Ok(windows)
}

fn parse_xid(xid: &str) -> Result<u64, String> {
    let clean = xid.trim();
    if let Some(stripped) = clean.strip_prefix("0x").or_else(|| clean.strip_prefix("0X")) {
        u64::from_str_radix(stripped, 16).map_err(|e| format!("Invalid hex XID '{xid}': {e}"))
    } else if let Ok(val) = clean.parse::<u64>() {
        Ok(val)
    } else {
        u64::from_str_radix(clean, 16).map_err(|e| format!("Invalid XID '{xid}': {e}"))
    }
}

#[tauri::command]
fn activate_window(window_id: String) -> Result<bool, String> {
    let wid = parse_xid(&window_id)?;

    unsafe {
        let display = XOpenDisplay(std::ptr::null());
        if display.is_null() {
            return Err("Cannot connect to X11 display".to_string());
        }

        let root = XDefaultRootWindow(display);
        let atom_name = std::ffi::CString::new("_NET_ACTIVE_WINDOW").map_err(|e| e.to_string())?;
        let net_active = XInternAtom(display, atom_name.as_ptr(), 0);

        let mut event: XEvent = std::mem::zeroed();
        event.xclient.type_ = 33; // ClientMessage
        event.xclient.send_event = 1;
        event.xclient.display = display;
        event.xclient.window = wid as c_ulong;
        event.xclient.message_type = net_active;
        event.xclient.format = 32;
        event.xclient.data[0] = 2; // Source: pager / taskbar
        event.xclient.data[1] = 0; // CurrentTime

        let mask = (1 << 19) | (1 << 20); // SubstructureNotifyMask | SubstructureRedirectMask
        XSendEvent(display, root, 0, mask, &mut event);
        XFlush(display);
        XCloseDisplay(display);
    }

    Ok(true)
}

#[tauri::command]
fn close_window(xid: String) -> Result<bool, String> {
    let wid = parse_xid(&xid)?;

    unsafe {
        let display = XOpenDisplay(std::ptr::null());
        if display.is_null() {
            return Err("Cannot connect to X11 display".to_string());
        }

        let root = XDefaultRootWindow(display);
        let atom_name = std::ffi::CString::new("_NET_CLOSE_WINDOW").map_err(|e| e.to_string())?;
        let net_close = XInternAtom(display, atom_name.as_ptr(), 0);

        let mut event: XEvent = std::mem::zeroed();
        event.xclient.type_ = 33; // ClientMessage
        event.xclient.send_event = 1;
        event.xclient.display = display;
        event.xclient.window = wid as c_ulong;
        event.xclient.message_type = net_close;
        event.xclient.format = 32;
        event.xclient.data[0] = 0; // CurrentTime
        event.xclient.data[1] = 2; // Source: pager / taskbar

        let mask = (1 << 19) | (1 << 20); // SubstructureNotifyMask | SubstructureRedirectMask
        XSendEvent(display, root, 0, mask, &mut event);
        XFlush(display);
        XCloseDisplay(display);
    }

    Ok(true)
}

#[tauri::command]
fn force_kill_window(xid: String) -> Result<bool, String> {
    let wid = parse_xid(&xid)?;

    // 1. Try finding PID via _NET_WM_PID property and terminate process
    let hex_id = format!("0x{:x}", wid);
    if let Ok(output) = Command::new("xprop")
        .args(["-id", &hex_id, "_NET_WM_PID"])
        .output()
    {
        let out_str = String::from_utf8_lossy(&output.stdout);
        if let Some(pid_str) = out_str.split('=').nth(1) {
            if let Ok(pid) = pid_str.trim().parse::<i32>() {
                if pid > 1 {
                    let _ = Command::new("kill").args(["-9", &pid.to_string()]).status();
                }
            }
        }
    }

    // 2. Instruct X server to close client connection immediately via XKillClient
    unsafe {
        let display = XOpenDisplay(std::ptr::null());
        if !display.is_null() {
            XKillClient(display, wid as c_ulong);
            XFlush(display);
            XCloseDisplay(display);
        }
    }

    Ok(true)
}

#[tauri::command]
fn spawn_app(exec_cmd: String) -> Result<bool, String> {
    let cmd = exec_cmd.trim();
    if cmd.is_empty() {
        return Err("Execution command cannot be empty".to_string());
    }

    std::process::Command::new("sh")
        .args(["-c", cmd])
        .spawn()
        .map(|_| true)
        .map_err(|e| format!("Failed to spawn app '{cmd}': {e}"))
}

#[tauri::command]
fn launch_app(command: String) -> Result<bool, String> {
    spawn_app(command)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let mut sys = System::new_all();
    sys.refresh_all();

    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .manage(AppState {
            sys: Mutex::new(sys),
        })
        .setup(|app| {
            if let Some(window) = app.get_webview_window("taskbar") {
                let _ = window.set_min_size(Some(PhysicalSize::new(100, 4)));
                let _ = reposition_taskbar(app.handle().clone(), "bottom".to_string(), Some(54));
                let _ = window.show();
            }
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::Focused(false) = event {
                if window.label() == "dock-context-menu" {
                    let _ = hide_dock_context_menu(window.app_handle().clone());
                }
            }
        })
        .invoke_handler(tauri::generate_handler![
            get_system_stats,
            get_wallpapers,
            get_current_wallpaper,
            set_wallpaper,
            toggle_taskbar,
            reposition_taskbar,
            is_autostart_enabled,
            set_autostart,
            install_app_icon,
            get_open_windows,
            activate_window,
            close_window,
            force_kill_window,
            spawn_app,
            launch_app,
            set_taskbar_autohide_state,
            set_taskbar_menu_expanded,
            show_dock_context_menu,
            hide_dock_context_menu
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
