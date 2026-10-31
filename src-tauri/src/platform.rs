use serde::Serialize;
use tauri::{AppHandle, Emitter, Manager};
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
    dock_placement: bool,
    auto_hide: bool,
    unavailable_reasons: std::collections::BTreeMap<String, String>,
    reasons: Vec<String>,
    monitors: Vec<MonitorInfo>,
}
pub fn dock_placement_available() -> bool {
    std::env::var("XDG_SESSION_TYPE").as_deref() == Ok("x11")
        && std::env::var("DISPLAY").is_ok_and(|display| !display.trim().is_empty())
}
fn unavailable_reasons(
    windows: crate::window_manager::Capabilities, probe_error: Option<&str>,
    wallpaper_error: Option<&str>, dock_placement: bool, xkill: bool,
) -> std::collections::BTreeMap<String, String> {
    let mut reasons = std::collections::BTreeMap::new();
    for (feature, available, fallback) in [
        ("windowEnumeration", windows.enumerate, "window_enumeration_unsupported"),
        ("windowActivation", windows.activate, "window_activation_unsupported"),
        ("windowClose", windows.close, "window_close_unsupported"),
    ] {
        if !available { reasons.insert(feature.into(), probe_error.unwrap_or(fallback).into()); }
    }
    if let Some(error) = wallpaper_error {
        reasons.insert("wallpaper".into(), error.split(':').next().unwrap_or(error).into());
    }
    if !dock_placement {
        reasons.insert("dockPlacement".into(), "dock_placement_unverified".into());
        reasons.insert("autoHide".into(), "dock_autohide_unverified".into());
    }
    if !windows.enumerate || !xkill {
        reasons.insert("forceQuit".into(), if !windows.enumerate { "window_enumeration_unsupported" } else { "xkill_unavailable" }.into());
    }
    reasons.insert("workspaces".into(), "workspaces_not_implemented".into());
    reasons
}
#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct MonitorInfo {
    primary: bool,
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
pub fn refresh_platform_info(app: AppHandle) -> Result<(), String> {
    app.state::<crate::window_manager::WindowSnapshots>().invalidate();
    app.emit("deskmorph:platform-changed", ()).map_err(|error| error.to_string())
}
#[tauri::command]
pub fn get_platform_info(app: AppHandle) -> Result<PlatformInfo, String> {
    let session = std::env::var("XDG_SESSION_TYPE").unwrap_or_else(|_| "unknown".into());
    let desktop = std::env::var("XDG_CURRENT_DESKTOP").unwrap_or_else(|_| "unknown".into());
    let probe = crate::window_manager::backend().and_then(|backend| backend.capabilities());
    let windows = probe.as_ref().copied().unwrap_or_default();
    let window_management = windows.enumerate;
    let wallpaper_status = crate::wallpaper::availability();
    let wallpaper = wallpaper_status.is_ok();
    let dock_placement = dock_placement_available();
    let xkill = executable_available("xkill");
    let unavailable_reasons = unavailable_reasons(windows, probe.as_ref().err().map(|error| error.code.as_str()),
        wallpaper_status.as_ref().err().map(String::as_str), dock_placement, xkill);
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
    if let Err(error) = wallpaper_status { reasons.push(error); }
    let window = app
        .get_webview_window("taskbar")
        .ok_or("Không tìm thấy Dock")?;
    let primary = window.primary_monitor().map_err(|e| e.to_string())?;
    let monitors = window
        .available_monitors()
        .map_err(|e| e.to_string())?
        .into_iter()
        .map(|m| MonitorInfo {
            primary: primary.as_ref().is_some_and(|p| p.position() == m.position() && p.name() == m.name()),
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
        force_quit: window_management && xkill,
        dock_placement,
        auto_hide: dock_placement,
        unavailable_reasons,
        reasons,
        monitors,
    })
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn missing_features_have_specific_reasons_and_development_is_explicit() {
        let windows = crate::window_manager::Capabilities { enumerate: true, activate: false, close: true };
        let reasons = unavailable_reasons(windows, None, Some("wallpaper_read_only: locked settings"), true, false);
        assert_eq!(reasons.get("windowActivation").map(String::as_str), Some("window_activation_unsupported"));
        assert!(!reasons.contains_key("windowEnumeration")); assert!(!reasons.contains_key("windowClose"));
        assert_eq!(reasons["wallpaper"], "wallpaper_read_only");
        assert_eq!(reasons["forceQuit"], "xkill_unavailable");
        assert_eq!(reasons["workspaces"], "workspaces_not_implemented");
        assert!(!reasons.contains_key("autoHide"));
        let reasons = unavailable_reasons(Default::default(), Some("window_backend_unsupported"), Some("wallpaper_adapter_unsupported"), false, true);
        for feature in ["windowEnumeration", "windowActivation", "windowClose"] {
            assert_eq!(reasons[feature], "window_backend_unsupported");
        }
        assert_eq!(reasons["dockPlacement"], "dock_placement_unverified");
        assert_eq!(reasons["autoHide"], "dock_autohide_unverified");
        let reasons = unavailable_reasons(Default::default(), Some("xprop_unavailable"), None, true, true);
        assert_eq!(reasons["windowEnumeration"], "xprop_unavailable");
        assert!(!reasons.contains_key("wallpaper"));
    }
}
