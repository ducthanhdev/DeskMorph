//! DisplayConfig read path. Mutation stays unavailable until a confirmation /
//! persistence / independent-recovery policy passes native acceptance.
use gio::{
    glib::{self, prelude::*, FromVariant, VariantDict},
    prelude::*,
};
use serde::Serialize;
use std::{
    collections::{HashMap, HashSet},
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc, Mutex,
    },
    thread::JoinHandle,
    time::{Duration, Instant},
};
use tauri::{AppHandle, Emitter, Manager};

const SERVICE: &str = "org.gnome.Mutter.DisplayConfig";
const PATH: &str = "/org/gnome/Mutter/DisplayConfig";
const STATE_TYPE: &str = "(ua((ssss)a(siiddada{sv})a{sv})a(iiduba(ssss)a{sv})a{sv})";

#[derive(Clone, Debug, Serialize)]
pub struct DisplayError {
    code: &'static str,
    message: String,
}
fn error(code: &'static str, message: impl ToString) -> DisplayError {
    DisplayError {
        code,
        message: message.to_string(),
    }
}
#[derive(Clone, Debug, Serialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct Capabilities {
    can_read: bool,
    can_set_primary: bool,
    can_persist: bool,
    recovery_available: bool,
    confirmation_owner: &'static str,
    reason: &'static str,
}
#[derive(Clone, Debug, Serialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct LogicalMonitor {
    id: String,
    name: String,
    connectors: Vec<String>,
    primary: bool,
    x: i32,
    y: i32,
    scale: f64,
    transform: u32,
}
#[derive(Clone, Debug, Serialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct PhysicalMonitor {
    connector: String,
    name: String,
    active: bool,
    logical_id: Option<String>,
    width: Option<i32>,
    height: Option<i32>,
    refresh_hz: Option<f64>,
}
#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Snapshot {
    revision: String,
    epoch: String,
    sequence: u64,
    capabilities: Capabilities,
    logical_monitors: Vec<LogicalMonitor>,
    physical_monitors: Vec<PhysicalMonitor>,
    transaction: Option<()>,
}
#[derive(PartialEq)]
struct Observed {
    owner: String,
    serial: u32,
    capabilities: Capabilities,
    logical: Vec<LogicalMonitor>,
    physical: Vec<PhysicalMonitor>,
}
struct Cache {
    epoch: String,
    sequence: u64,
    observed: Option<Observed>,
    snapshot: Option<Snapshot>,
}
impl Default for Cache {
    fn default() -> Self {
        Self {
            epoch: glib::uuid_string_random().to_string(),
            sequence: 0,
            observed: None,
            snapshot: None,
        }
    }
}
#[derive(Default)]
pub struct DisplayState {
    cache: Arc<Mutex<Cache>>,
    read_lock: Arc<Mutex<()>>,
    stop: Arc<AtomicBool>,
    worker: Mutex<Option<JoinHandle<()>>>,
}
fn field<T: glib::variant::FromVariant>(
    value: &glib::Variant,
    index: usize,
) -> Result<T, DisplayError> {
    if !value.is_container() || index >= value.n_children() {
        return Err(error(
            "display_response_invalid",
            "Missing display response field",
        ));
    }
    value
        .child_value(index)
        .get()
        .ok_or_else(|| error("display_response_invalid", "Invalid display response field"))
}
fn properties(value: &glib::Variant) -> Result<VariantDict, DisplayError> {
    VariantDict::from_variant(value)
        .ok_or_else(|| error("display_response_invalid", "Invalid display properties"))
}
fn prop<T: glib::variant::FromVariant>(dict: &VariantDict, key: &str) -> Option<T> {
    dict.lookup(key).ok().flatten()
}
fn capabilities(can_read: bool, allowed: bool) -> Capabilities {
    Capabilities {
        can_read,
        can_set_primary: false,
        can_persist: false,
        recovery_available: false,
        confirmation_owner: "unavailable",
        reason: if !can_read {
            "display_unsupported"
        } else if !allowed {
            "display_permission_denied"
        } else {
            "display_recovery_unverified"
        },
    }
}
fn parse(value: &glib::Variant, owner: String, allowed: bool) -> Result<Observed, DisplayError> {
    if value.type_().as_str() != STATE_TYPE || value.size() > 256 * 1024 {
        return Err(error(
            "display_response_invalid",
            "Unexpected or oversized display response",
        ));
    }
    let physical = value.child_value(1);
    let logical = value.child_value(2);
    if physical.n_children() > 64 || logical.n_children() > 64 {
        return Err(error("display_response_invalid", "Too many displays"));
    }
    let mut monitors = Vec::new();
    for i in 0..physical.n_children() {
        let item = physical.child_value(i);
        let spec = item.child_value(0);
        let connector: String = field(&spec, 0)?;
        let props = properties(&item.child_value(2))?;
        let name = prop::<String>(&props, "display-name")
            .filter(|v| !v.trim().is_empty())
            .unwrap_or_else(|| connector.clone());
        let modes = item.child_value(1);
        if modes.n_children() > 512 {
            return Err(error("display_response_invalid", "Too many display modes"));
        }
        let mut current = None;
        for j in 0..modes.n_children() {
            let mode = modes.child_value(j);
            if prop::<bool>(&properties(&mode.child_value(6))?, "is-current") == Some(true) {
                if current.is_some() {
                    return Err(error(
                        "display_response_invalid",
                        "Multiple current display modes",
                    ));
                }
                let (width, height, hz): (i32, i32, f64) =
                    (field(&mode, 1)?, field(&mode, 2)?, field(&mode, 3)?);
                if width <= 0 || height <= 0 || !hz.is_finite() || hz <= 0. {
                    return Err(error("display_response_invalid", "Invalid display mode"));
                }
                current = Some((width, height, hz));
            }
        }
        monitors.push(PhysicalMonitor {
            connector,
            name,
            active: false,
            logical_id: None,
            width: current.map(|m| m.0),
            height: current.map(|m| m.1),
            refresh_hz: current.map(|m| m.2),
        });
    }
    let names: HashMap<_, _> = monitors
        .iter()
        .map(|m| (m.connector.clone(), m.name.clone()))
        .collect();
    if names.len() != monitors.len() {
        return Err(error(
            "display_response_invalid",
            "Duplicate display connector",
        ));
    }
    let mut seen = HashSet::new();
    let mut groups = Vec::new();
    for i in 0..logical.n_children() {
        let item = logical.child_value(i);
        let specs = item.child_value(5);
        let mut connectors = Vec::new();
        for j in 0..specs.n_children() {
            let connector: String = field(&specs.child_value(j), 0)?;
            if !names.contains_key(&connector) || !seen.insert(connector.clone()) {
                return Err(error(
                    "display_response_invalid",
                    "Invalid logical display membership",
                ));
            }
            connectors.push(connector);
        }
        if connectors.is_empty() {
            return Err(error("display_response_invalid", "Empty logical display"));
        }
        connectors.sort();
        // JSON encoding avoids ambiguous IDs when connector names contain separators.
        let id =
            serde_json::to_string(&connectors).map_err(|e| error("display_response_invalid", e))?;
        let scale: f64 = field(&item, 2)?;
        let transform: u32 = field(&item, 3)?;
        if !scale.is_finite() || scale <= 0. || transform > 7 {
            return Err(error(
                "display_response_invalid",
                "Invalid scale or transform",
            ));
        }
        groups.push(LogicalMonitor {
            name: connectors
                .iter()
                .map(|c| names[c].as_str())
                .collect::<Vec<_>>()
                .join(" + "),
            id,
            connectors,
            primary: field(&item, 4)?,
            x: field(&item, 0)?,
            y: field(&item, 1)?,
            scale,
            transform,
        });
    }
    if !groups.is_empty() && groups.iter().filter(|m| m.primary).count() != 1 {
        return Err(error(
            "display_response_invalid",
            "Expected one active primary display",
        ));
    }
    for monitor in &mut monitors {
        if let Some(group) = groups
            .iter()
            .find(|g| g.connectors.contains(&monitor.connector))
        {
            if monitor.width.is_none() {
                return Err(error(
                    "display_response_invalid",
                    "Active display has no current mode",
                ));
            }
            monitor.active = true;
            monitor.logical_id = Some(group.id.clone());
        }
    }
    groups.sort_by(|a, b| a.id.cmp(&b.id));
    monitors.sort_by(|a, b| a.connector.cmp(&b.connector));
    Ok(Observed {
        owner,
        serial: field(value, 0)?,
        capabilities: capabilities(true, allowed),
        logical: groups,
        physical: monitors,
    })
}
fn call(
    bus: &gio::DBusConnection,
    destination: &str,
    path: &str,
    interface: &str,
    method: &str,
    args: Option<&glib::Variant>,
) -> Result<glib::Variant, DisplayError> {
    bus.call_sync(
        Some(destination),
        path,
        interface,
        method,
        args,
        None,
        gio::DBusCallFlags::NO_AUTO_START,
        1500,
        gio::Cancellable::NONE,
    )
    .map_err(|e| error("display_read_failed", e))
}
fn read() -> Result<Observed, DisplayError> {
    let bus = gio::bus_get_sync(gio::BusType::Session, gio::Cancellable::NONE)
        .map_err(|e| error("display_read_failed", e))?;
    bus.set_exit_on_close(false);
    // Absence is a capability, not a reason to launch a compositor on this bus.
    let exists = call(
        &bus,
        "org.freedesktop.DBus",
        "/org/freedesktop/DBus",
        "org.freedesktop.DBus",
        "NameHasOwner",
        Some(&(SERVICE,).to_variant()),
    )?;
    if !field::<bool>(&exists, 0)? {
        return Ok(Observed {
            owner: format!("{}:unavailable", bus.guid()),
            serial: 0,
            capabilities: capabilities(false, false),
            logical: vec![],
            physical: vec![],
        });
    }
    let owner: String = field(
        &call(
            &bus,
            "org.freedesktop.DBus",
            "/org/freedesktop/DBus",
            "org.freedesktop.DBus",
            "GetNameOwner",
            Some(&(SERVICE,).to_variant()),
        )?,
        0,
    )?;
    let response = call(&bus, &owner, PATH, SERVICE, "GetCurrentState", None)?;
    let props = call(
        &bus,
        &owner,
        PATH,
        "org.freedesktop.DBus.Properties",
        "GetAll",
        Some(&(SERVICE,).to_variant()),
    )?;
    if props.type_().as_str() != "(a{sv})" {
        return Err(error(
            "display_response_invalid",
            "Invalid service properties response",
        ));
    }
    let allowed = prop::<bool>(
        &properties(&props.child_value(0))?,
        "ApplyMonitorsConfigAllowed",
    )
    .unwrap_or(false);
    // Unique names and serials may both be reused after a session-bus restart.
    let observed = parse(&response, format!("{}:{owner}", bus.guid()), allowed)?;
    let after: String = field(
        &call(
            &bus,
            "org.freedesktop.DBus",
            "/org/freedesktop/DBus",
            "org.freedesktop.DBus",
            "GetNameOwner",
            Some(&(SERVICE,).to_variant()),
        )?,
        0,
    )?;
    if after != owner {
        return Err(error(
            "display_stale_revision",
            "Display service restarted during read",
        ));
    }
    Ok(observed)
}
fn requires_layout(previous: Option<&Observed>, next: &Observed) -> bool {
    // Startup/config already lays out the Dock. A delayed first read, permission
    // change or serial-only publication must not dismiss an active interaction.
    previous.is_some_and(|previous| {
        previous.logical != next.logical || previous.physical != next.physical
    })
}
fn refresh(app: &AppHandle) -> Result<Snapshot, DisplayError> {
    let state = app.state::<DisplayState>();
    let _read = state
        .read_lock
        .lock()
        .map_err(|e| error("display_read_failed", e))?;
    let observed = read()?;
    let mut cache = state
        .cache
        .lock()
        .map_err(|e| error("display_read_failed", e))?;
    let changed = cache.observed.as_ref() != Some(&observed);
    let layout_changed = requires_layout(cache.observed.as_ref(), &observed);
    if changed || cache.snapshot.is_none() {
        cache.sequence += 1;
        let snapshot = Snapshot {
            revision: format!("{}:{}", cache.epoch, cache.sequence),
            epoch: cache.epoch.clone(),
            sequence: cache.sequence,
            capabilities: observed.capabilities.clone(),
            logical_monitors: observed.logical.clone(),
            physical_monitors: observed.physical.clone(),
            transaction: None,
        };
        cache.observed = Some(observed);
        cache.snapshot = Some(snapshot);
    }
    let snapshot = cache.snapshot.as_ref().unwrap().clone();
    drop(cache);
    if changed {
        let _ = app.emit("deskmorph:display-state", &snapshot);
        let handle = app.clone();
        // GTK operations stay on the main context, never on the D-Bus reader.
        let _ = app.run_on_main_thread(move || {
            if layout_changed {
                let _ = crate::popup::hide(&handle, "dock-context-menu", None);
                let _ = crate::popup::hide(&handle, "calendar-flyout", None);
                let _ = crate::layout::apply(&handle);
            }
            let _ = handle.emit("deskmorph:platform-changed", ());
        });
    }
    Ok(snapshot)
}
#[tauri::command]
pub async fn get_display_state(app: AppHandle) -> Result<Snapshot, DisplayError> {
    tauri::async_runtime::spawn_blocking(move || refresh(&app))
        .await
        .map_err(|e| error("display_read_failed", e))?
}
#[tauri::command]
pub async fn open_display_settings(window: tauri::WebviewWindow) -> Result<(), DisplayError> {
    if window.label() != "main" {
        return Err(error(
            "display_permission_denied",
            "Display Settings is available from Studio",
        ));
    }
    tauri::async_runtime::spawn_blocking(|| {
        // GIO parses the installed desktop entry; no connector/user text enters a shell.
        let entry = gio::DesktopAppInfo::new("gnome-display-panel.desktop").ok_or_else(|| {
            error(
                "display_settings_missing",
                "Display Settings is not installed",
            )
        })?;
        entry
            .launch(&[], gio::AppLaunchContext::NONE)
            .map_err(|e| error("display_settings_open_failed", e))
    })
    .await
    .map_err(|e| error("display_settings_open_failed", e))?
}
pub fn start(app: &AppHandle) {
    let handle = app.clone();
    let state = app.state::<DisplayState>();
    let stop = state.stop.clone();
    let worker = std::thread::spawn(move || {
        let context = glib::MainContext::new();
        let _ = context.with_thread_default(|| {
            let mut bus = None;
            let mut subscriptions = Vec::new();
            let dirty = Arc::new(AtomicBool::new(true));
            let mut last = Instant::now() - Duration::from_secs(5);
            let mut failed = false;
            while !stop.load(Ordering::Relaxed) {
                if bus
                    .as_ref()
                    .is_none_or(|b: &gio::DBusConnection| b.is_closed())
                {
                    if let Some(previous) = bus.take() {
                        for id in subscriptions.drain(..) {
                            previous.signal_unsubscribe(id);
                        }
                    }
                    if let Ok(connection) =
                        gio::bus_get_sync(gio::BusType::Session, gio::Cancellable::NONE)
                    {
                        let changed = dirty.clone();
                        subscriptions.push(connection.signal_subscribe(
                            Some(SERVICE),
                            Some(SERVICE),
                            Some("MonitorsChanged"),
                            Some(PATH),
                            None,
                            gio::DBusSignalFlags::NONE,
                            move |_, _, _, _, _, _| {
                                changed.store(true, Ordering::Relaxed);
                            },
                        ));
                        let changed = dirty.clone();
                        subscriptions.push(connection.signal_subscribe(
                            Some("org.freedesktop.DBus"),
                            Some("org.freedesktop.DBus"),
                            Some("NameOwnerChanged"),
                            Some("/org/freedesktop/DBus"),
                            Some(SERVICE),
                            gio::DBusSignalFlags::NONE,
                            move |_, _, _, _, _, _| {
                                changed.store(true, Ordering::Relaxed);
                            },
                        ));
                        bus = Some(connection);
                    }
                }
                while context.pending() {
                    context.iteration(false);
                }
                if dirty.swap(false, Ordering::Relaxed) || last.elapsed() >= Duration::from_secs(5)
                {
                    match refresh(&handle) {
                        Ok(snapshot) => {
                            if failed {
                                let _ = handle.emit("deskmorph:display-state", snapshot);
                            }
                            failed = false;
                        }
                        Err(e) => {
                            failed = true;
                            let _ = handle.emit("deskmorph:display-read-error", e);
                        }
                    }
                    last = Instant::now();
                }
                std::thread::sleep(Duration::from_millis(150));
            }
            if let Some(bus) = bus {
                for id in subscriptions {
                    bus.signal_unsubscribe(id);
                }
            }
        });
    });
    if let Ok(mut slot) = state.worker.lock() {
        *slot = Some(worker);
    };
}
pub fn stop(app: &AppHandle) {
    let state = app.state::<DisplayState>();
    state.stop.store(true, Ordering::Relaxed);
    // Do not block GTK while a reader may be posting its final main-context work.
    if let Ok(mut worker) = state.worker.lock() {
        if let Some(worker) = worker.take() {
            let _ = worker.join();
        }
    };
}

#[cfg(test)]
mod tests {
    use super::*;
    fn fixture(groups: &str) -> glib::Variant {
        let text = format!(
            r#"(uint32 7,
          [(('eDP-1','Acme','Panel','private-device-id'),
            [('1920x1080@60',1920,1080,60.0,1.0,[1.0],{{'is-current': <true>}})],{{'display-name': <'Laptop'>}}),
           (('HDMI-1','Acme','Panel','another-private-id'),
            [('1280x720@75',1280,720,75.0,1.0,[1.0],{{'is-current': <true>}})],{{'display-name': <'External'>}})],
          {groups}, {{}})"#
        );
        glib::Variant::parse(Some(glib::VariantTy::new(STATE_TYPE).unwrap()), &text).unwrap()
    }
    fn separate(primary_a: bool) -> glib::Variant {
        fixture(&format!("[(0,0,1.0,uint32 0,{primary_a},[('eDP-1','Acme','Panel','private-device-id')],{{}}), (1920,0,1.0,uint32 0,{},[('HDMI-1','Acme','Panel','another-private-id')],{{}})]",!primary_a))
    }
    #[test]
    fn reads_primary_modes_and_connector_identity_without_exposing_device_serials() {
        let state = parse(&separate(true), ":1.1".into(), true).unwrap();
        assert!(
            state
                .logical
                .iter()
                .find(|m| m.connectors == ["eDP-1"])
                .unwrap()
                .primary
        );
        assert_eq!(
            state
                .physical
                .iter()
                .find(|m| m.connector == "HDMI-1")
                .unwrap()
                .refresh_hz,
            Some(75.)
        );
        assert_eq!(state.capabilities.reason, "display_recovery_unverified");
        assert!(!state.capabilities.can_set_primary);
        let public = serde_json::to_string(&state.physical).unwrap();
        assert!(!public.contains("private-id") && !public.contains("private-device-id"));
    }
    #[test]
    fn primary_changes_are_observed_even_if_geometry_and_serial_are_identical() {
        let first = parse(&separate(true), ":1.1".into(), true).unwrap();
        let second = parse(&separate(false), ":1.1".into(), true).unwrap();
        assert!(first != second);
        assert_eq!(
            first.logical.iter().map(|m| (m.x, m.y)).collect::<Vec<_>>(),
            second
                .logical
                .iter()
                .map(|m| (m.x, m.y))
                .collect::<Vec<_>>()
        );
    }
    #[test]
    fn mirror_is_one_logical_target_and_inactive_outputs_remain_visible() {
        let mirrored=fixture("[(0,0,1.0,uint32 0,true,[('HDMI-1','Acme','Panel','another-private-id'),('eDP-1','Acme','Panel','private-device-id')],{})]");
        let state = parse(&mirrored, ":1.1".into(), true).unwrap();
        assert_eq!(state.logical.len(), 1);
        assert!(state
            .physical
            .iter()
            .all(|m| m.active && m.logical_id == Some(state.logical[0].id.clone())));
        let one =
            fixture("[(0,0,1.0,uint32 0,true,[('eDP-1','Acme','Panel','private-device-id')],{})]");
        let state = parse(&one, ":1.1".into(), true).unwrap();
        assert!(
            !state
                .physical
                .iter()
                .find(|m| m.connector == "HDMI-1")
                .unwrap()
                .active
        );
    }
    #[test]
    fn invalid_primary_membership_scale_and_response_are_rejected() {
        for groups in [
            "[(0,0,1.0,uint32 0,false,[('eDP-1','Acme','Panel','private-device-id')],{})]",
            "[(0,0,1.0,uint32 0,true,[('missing','Acme','Panel','id')],{})]",
            "[(0,0,0.0,uint32 0,true,[('eDP-1','Acme','Panel','private-device-id')],{})]",
            "[(0,0,1.0,uint32 0,true,[('eDP-1','Acme','Panel','private-device-id')],{}),(100,0,1.0,uint32 0,false,[('eDP-1','Acme','Panel','private-device-id')],{})]",
        ] {
            assert!(parse(&fixture(groups),":1.1".into(),true).is_err());
        }
        assert!(parse(&"bad".to_variant(), ":1.1".into(), true).is_err());
    }
    #[test]
    fn service_owner_and_permissions_are_part_of_observed_state() {
        let first = parse(&separate(true), ":1.1".into(), true).unwrap();
        let restarted = parse(&separate(true), ":1.2".into(), true).unwrap();
        let denied = parse(&separate(true), ":1.1".into(), false).unwrap();
        assert!(first != restarted && first != denied);
        assert_eq!(denied.capabilities.reason, "display_permission_denied");
        assert!(!denied.capabilities.can_set_primary);
    }
    #[test]
    fn startup_and_metadata_publications_do_not_interrupt_popups_but_primary_changes_do() {
        let first = parse(&separate(true), ":1.1".into(), true).unwrap();
        assert!(!requires_layout(None, &first));
        let mut metadata = parse(&separate(true), "new-bus/:1.1".into(), false).unwrap();
        metadata.serial += 1;
        assert!(!requires_layout(Some(&first), &metadata));
        let changed_primary = parse(&separate(false), ":1.1".into(), true).unwrap();
        assert!(requires_layout(Some(&first), &changed_primary));
    }
}
