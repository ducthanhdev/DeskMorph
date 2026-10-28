//! Optional read-only system services. One cached source is shared by Dock and popup.
use gio::{glib::{self, prelude::*, FromVariant, VariantDict}, prelude::*};
use serde::Serialize;
use std::{sync::{Arc, Mutex}, time::{Duration, Instant}};
use tauri::{AppHandle, Manager};
#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Battery { percentage: f64, state: String, remaining_seconds: Option<i64> }
#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Network { kind: String, state: String, connectivity: String }
#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Status { battery: Option<Battery>, battery_error: Option<String>, network: Option<Network>, network_error: Option<String>, monitor_id: Option<String>, folder_available: bool, trash_available: bool }
#[derive(Default)]
pub struct SystemStatusState(Arc<Mutex<Option<(Instant, Status)>>>);
fn properties(bus: &gio::DBusConnection, name: &str, path: &str, interface: &str) -> Result<VariantDict, String> {
    let reply = bus.call_sync(Some(name), path, "org.freedesktop.DBus.Properties", "GetAll", Some(&(interface,).to_variant()), Some(glib::VariantTy::new("(a{sv})").unwrap()), gio::DBusCallFlags::NO_AUTO_START, 1000, gio::Cancellable::NONE).map_err(|e| e.to_string())?;
    VariantDict::from_variant(&reply.child_value(0)).ok_or("system_service_response".into())
}
fn value<T: glib::variant::FromVariant>(dict: &VariantDict, key: &str) -> Option<T> { dict.lookup(key).ok().flatten() }
fn battery_from(dict: &VariantDict) -> Result<Option<Battery>, String> {
    let present = value::<bool>(dict, "IsPresent").ok_or("battery_invalid_presence")?;
    if !present { return Ok(None); }
    let kind = value::<u32>(dict, "Type").ok_or("battery_invalid_type")?;
    if kind != 2 { return Ok(None); }
    let percentage = value::<f64>(dict, "Percentage").filter(|n| n.is_finite() && (0.0..=100.0).contains(n)).ok_or("battery_invalid_percentage")?;
    let code = value::<u32>(dict, "State").unwrap_or(0);
    let state = match code { 1 => "charging", 2 => "discharging", 3 => "empty", 4 => "charged", 5 => "pendingCharge", 6 => "pendingDischarge", _ => "unknown" };
    let remaining_seconds = match code { 1 => value::<i64>(dict, "TimeToFull"), 2 => value::<i64>(dict, "TimeToEmpty"), _ => None }.filter(|seconds| *seconds > 0);
    Ok(Some(Battery { percentage, state: state.into(), remaining_seconds }))
}
fn battery(bus: &gio::DBusConnection) -> Result<Option<Battery>, String> {
    let reply = bus.call_sync(Some("org.freedesktop.UPower"), "/org/freedesktop/UPower", "org.freedesktop.UPower", "GetDisplayDevice", None, Some(glib::VariantTy::new("(o)").unwrap()), gio::DBusCallFlags::NO_AUTO_START, 1000, gio::Cancellable::NONE).map_err(|e| e.to_string())?;
    let path = reply.child_value(0);
    battery_from(&properties(bus, "org.freedesktop.UPower", path.str().ok_or("battery_display_device")?, "org.freedesktop.UPower.Device")?)
}
fn network_from(dict: &VariantDict) -> Result<Network, String> {
    let state = value::<u32>(dict, "State").ok_or("network_invalid_state")?;
    let state = match state { 10 => "asleep", 20 => "disconnected", 30 => "disconnecting", 40 => "connecting", 50 => "local", 60 => "site", 70 => "global", _ => "unknown" };
    let kind = match value::<String>(dict, "PrimaryConnectionType").as_deref() { Some("802-11-wireless") => "wifi", Some("802-3-ethernet") => "wired", _ => "other" };
    let connectivity = match value::<u32>(dict, "Connectivity") { Some(1) => "none", Some(2) => "portal", Some(3) => "limited", Some(4) => "full", _ => "unknown" };
    Ok(Network { kind: kind.into(), state: state.into(), connectivity: connectivity.into() })
}
const MONITORS: &[&str] = &["org.gnome.SystemMonitor.desktop", "gnome-system-monitor.desktop", "org.gnome.Usage.desktop", "org.kde.plasma-systemmonitor.desktop", "plasma-systemmonitor.desktop", "ksysguard.desktop"];
fn monitor_id() -> Option<String> {
    let apps = gio::AppInfo::all();
    MONITORS.iter().find(|id| apps.iter().any(|app| app.id().is_some_and(|name| name == **id) && app.should_show())).map(|id| id.to_string())
}
fn folder_app() -> Option<gio::AppInfo> {
    let file_manager = |app: &gio::AppInfo| app.should_show() && app.downcast_ref::<gio::DesktopAppInfo>().and_then(|app| app.categories()).is_some_and(|categories| categories.split(';').any(|category| category == "FileManager"));
    if let Some(app) = gio::AppInfo::default_for_type("inode/directory", false).filter(file_manager) { return Some(app); }
    let mut apps: Vec<_> = gio::AppInfo::all().into_iter().filter(file_manager).collect();
    apps.sort_by_key(|app| app.id()); apps.into_iter().next()
}
fn read() -> Status {
    let (battery, network) = match gio::bus_get_sync(gio::BusType::System, gio::Cancellable::NONE) {
        Ok(bus) => { bus.set_exit_on_close(false); (battery(&bus), properties(&bus, "org.freedesktop.NetworkManager", "/org/freedesktop/NetworkManager", "org.freedesktop.NetworkManager").and_then(|props| network_from(&props))) },
        Err(_) => (Err("system_bus_unavailable".into()), Err("system_bus_unavailable".into())),
    };
    let (battery, battery_error) = match battery { Ok(value) => (value, None), Err(_) => (None, Some("battery_service_unavailable".into())) };
    let (network, network_error) = match network { Ok(value) => (Some(value), None), Err(_) => (None, Some("network_service_unavailable".into())) };
    Status { battery, battery_error, network, network_error, monitor_id: monitor_id(), folder_available: folder_app().is_some(), trash_available: gio::AppInfo::default_for_uri_scheme("trash").is_some() }
}
#[tauri::command]
pub async fn get_system_status(app: AppHandle) -> Result<Status, String> {
    let cache = app.state::<SystemStatusState>().0.clone();
    tauri::async_runtime::spawn_blocking(move || {
        let mut cache = cache.lock().map_err(|e| e.to_string())?;
        if let Some((at, status)) = &*cache { if at.elapsed() < Duration::from_secs(5) { return Ok(status.clone()); } }
        let status = read(); *cache = Some((Instant::now(), status.clone())); Ok(status)
    }).await.map_err(|e| e.to_string())?
}
fn open_location(location: &str) -> Result<(), String> {
    match location {
        "downloads" => {
            let path = glib::user_special_dir(glib::UserDirectory::Downloads).unwrap_or_else(|| glib::home_dir().join("Downloads"));
            if !path.is_dir() { return Err("downloads_missing".into()); }
            let app = folder_app().ok_or("file_manager_missing")?;
            if app.id().as_deref() == Some("com.system76.CosmicFiles.desktop") {
                // COSMIC Files 1.11 accepts native paths; its %U entry can ignore unsupported URIs.
                let mut child = std::process::Command::new(app.executable()).arg(&path).spawn().map_err(|e| format!("system_open_failed: {e}"))?;
                std::thread::spawn(move || { let _ = child.wait(); });
                Ok(())
            } else {
                app.launch(&[gio::File::for_path(path)], gio::AppLaunchContext::NONE).map_err(|e| format!("system_open_failed: {e}"))
            }
        },
        "trash" => {
            if gio::AppInfo::default_for_uri_scheme("trash").is_none() { return Err("trash_unsupported".into()); }
            gio::AppInfo::launch_default_for_uri("trash:///", gio::AppLaunchContext::NONE).map_err(|e| format!("system_open_failed: {e}"))
        },
        "monitor" => {
            let id = monitor_id().ok_or("system_monitor_missing")?;
            crate::applications::launch_installed_app(id, None)?; Ok(())
        },
        _ => Err("system_location_invalid".into()),
    }
}
#[tauri::command]
pub async fn open_system_location(location: String) -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(move || open_location(&location)).await.map_err(|e| e.to_string())?
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn battery_aggregate_presence_state_and_estimate_are_not_invented() {
        let dict = VariantDict::default(); dict.insert("IsPresent", false); assert!(battery_from(&dict).unwrap().is_none());
        dict.insert("IsPresent", true); dict.insert("Type", 2u32); dict.insert("Percentage", 79.5f64); dict.insert("State", 2u32); dict.insert("TimeToEmpty", 0i64);
        let result = battery_from(&dict).unwrap().unwrap(); assert_eq!(result.percentage, 79.5); assert!(result.remaining_seconds.is_none());
        dict.insert("TimeToEmpty", 3600i64); assert_eq!(battery_from(&dict).unwrap().unwrap().remaining_seconds, Some(3600));
        dict.insert("State", 4u32); assert!(battery_from(&dict).unwrap().unwrap().remaining_seconds.is_none());
        dict.insert("Percentage", 101f64); assert!(battery_from(&dict).is_err());
    }
    #[test]
    fn local_network_is_distinct_from_connectivity_probe() {
        let dict = VariantDict::default(); dict.insert("State", 50u32); dict.insert("PrimaryConnectionType", "802-11-wireless"); dict.insert("Connectivity", 3u32);
        let result = network_from(&dict).unwrap(); assert_eq!(result.state, "local"); assert_eq!(result.kind, "wifi"); assert_eq!(result.connectivity, "limited");
        dict.insert("State", 20u32); dict.insert("Connectivity", 0u32); let result = network_from(&dict).unwrap(); assert_eq!(result.state, "disconnected"); assert_eq!(result.connectivity, "unknown");
    }
}
