use serde::Serialize;
use tauri::{AppHandle, Manager};
#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PlatformInfo {
    session: String,
    desktop: String,
    window_management: bool,
    windows: crate::window_manager::Capabilities,
    wallpaper: bool,
    workspaces: bool,
    force_quit: bool,
    reasons: Vec<String>,
    monitors: Vec<MonitorInfo>,
}
#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct MonitorInfo {
    name: String,
    x: i32,
    y: i32,
    width: u32,
    height: u32,
    scale: f64,
}
pub fn executable_available(name: &str) -> bool {
    use std::os::unix::fs::PermissionsExt;
    std::env::var_os("PATH").is_some_and(|paths| {
        std::env::split_paths(&paths).any(|p| {
            std::fs::metadata(p.join(name))
                .is_ok_and(|m| m.is_file() && m.permissions().mode() & 0o111 != 0)
        })
    })
}
#[tauri::command]
pub fn get_platform_info(app: AppHandle) -> Result<PlatformInfo, String> {
    let session = std::env::var("XDG_SESSION_TYPE").unwrap_or_else(|_| "unknown".into());
    let desktop = std::env::var("XDG_CURRENT_DESKTOP").unwrap_or_else(|_| "unknown".into());
    let probe = crate::window_manager::backend().and_then(|backend| backend.capabilities());
    let windows = probe.as_ref().copied().unwrap_or_default();
    let window_management = windows.enumerate;
    let wallpaper = crate::wallpaper::available();
    let mut reasons = Vec::new();
    match probe {
        Err(error) => reasons.push(error.to_string()),
        Ok(caps) => {
            if !caps.enumerate {
                reasons.push("window_enumeration_unsupported: Window manager không cung cấp _NET_CLIENT_LIST.".into());
            }
            if !caps.activate {
                reasons.push("window_activation_unsupported: Window manager không công bố _NET_ACTIVE_WINDOW.".into());
            }
            if !caps.close {
                reasons.push(
                    "window_close_unsupported: Window manager không công bố _NET_CLOSE_WINDOW."
                        .into(),
                );
            }
        }
    }
    if !wallpaper {
        reasons.push(
            "Đổi hình nền hiện chỉ có adapter GNOME; desktop khác chưa được xác minh.".into(),
        );
    }
    let window = app
        .get_webview_window("taskbar")
        .ok_or("Không tìm thấy Dock")?;
    let monitors = window
        .available_monitors()
        .map_err(|e| e.to_string())?
        .into_iter()
        .map(|m| MonitorInfo {
            name: m.name().cloned().unwrap_or_else(|| "Monitor".into()),
            x: m.position().x,
            y: m.position().y,
            width: m.size().width,
            height: m.size().height,
            scale: m.scale_factor(),
        })
        .collect();
    Ok(PlatformInfo {
        session,
        desktop,
        window_management,
        windows,
        wallpaper,
        workspaces: false,
        force_quit: window_management && executable_available("xkill"),
        reasons,
        monitors,
    })
}
