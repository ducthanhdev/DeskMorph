//! Versioned configuration. All mutations are serialized by one managed mutex.
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::os::unix::fs::OpenOptionsExt;
use std::{fs, io::Write, path::{Path, PathBuf}, sync::Mutex};
use tauri::{AppHandle, Emitter, Manager};

const VERSION: u32 = 1;

#[derive(Debug, Serialize)]
pub struct ConfigError {
    code: &'static str,
    message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    context: Option<Value>,
}
impl ConfigError {
    fn new(code: &'static str, message: impl ToString) -> Self { Self { code, message: message.to_string(), context: None } }
}
type Result<T> = std::result::Result<T, ConfigError>;

#[derive(Clone, Serialize, Deserialize, Debug)]
#[serde(rename_all = "camelCase")]
pub struct Snapshot {
    pub schema_version: u32,
    pub revision: u64,
    pub config: Value,
    pub warning: Option<String>,
}

pub fn defaults() -> Value {
    serde_json::from_str(include_str!("../../src/config/defaults.json")).expect("bundled defaults must be valid JSON")
}

fn valid_color(v: &Value) -> bool {
    v.as_str().is_some_and(|s| s.len() == 7 && s.starts_with('#') && s[1..].bytes().all(|b| b.is_ascii_hexdigit()))
}
fn validate_pin(v: &Value) -> bool {
    let strings = ["id", "name", "command"];
    v.is_object() && strings.iter().all(|k| v[*k].as_str().is_some_and(|s| !s.trim().is_empty() && s.len() <= 4096))
        && v["matchClasses"].as_array().is_some_and(|a| a.len() <= 64 && a.iter().all(|s| s.as_str().is_some_and(|s| !s.is_empty() && s.len() <= 256)))
        && matches!(v["iconType"].as_str(), Some("chrome" | "terminal" | "code" | "files" | "settings" | "browser" | "custom"))
        && (v.get("desktopId").is_none() || v["desktopId"].as_str().is_some_and(|s| s.ends_with(".desktop") && s.len() <= 512))
        && (v.get("color").is_none() || valid_color(&v["color"]))
        && (v.get("enabled").is_none() || v["enabled"].is_boolean())
}
// Match the explicit identities understood by the frontend. Legacy argv stays
// opaque here: WM_CLASS/executable guesses must never merge unrelated pins.
fn pin_desktop_id(pin: &Value) -> Option<&str> {
    if let Some(id) = pin["desktopId"].as_str() { return Some(id); }
    let command = pin["command"].as_str()?.trim();
    if let Some(id) = command.strip_prefix("desktop:") { return Some(id); }
    (command.ends_with(".desktop") && !command.chars().any(|c| c.is_whitespace() || c == '/')).then_some(command)
}

// Older versions allowed different pin IDs for one desktop identity. Preserve
// the first pin's order/metadata and keep it enabled if any duplicate was enabled.
// A recovery copy/localStorage keeps the original document for load/migration.
fn repair_duplicate_desktop_pins(value: &Value) -> Option<Value> {
    let pins = value.as_array()?;
    let mut ids = std::collections::HashSet::new();
    if pins.len() > 256 || !pins.iter().all(|p| validate_pin(p) && ids.insert(p["id"].as_str().unwrap())) { return None; }
    let mut unique: Vec<Value> = Vec::new();
    let mut repaired = false;
    for pin in pins {
        if let Some(index) = pin_desktop_id(pin).and_then(|id| unique.iter().position(|other| pin_desktop_id(other) == Some(id))) {
            repaired = true;
            if pin["enabled"].as_bool() != Some(false) { unique[index]["enabled"] = json!(true); }
        } else { unique.push(pin.clone()); }
    }
    repaired.then(|| json!(unique))
}

fn valid_field(key: &str, v: &Value) -> bool {
    match key {
        "launcherShortcut" => v.is_null() || v.as_str().is_some_and(super::shortcuts::valid),
        "wallpaperScheduleEnabled" | "wallpaperRecursive" | "clock24" | "clockSeconds" | "reduceMotion" | "keepDockOnClose" | "enabled" | "autoHide" | "showBattery" | "showNetwork" | "showSystem" | "showAudio" | "showClock" | "showStats" | "showShuffle" | "showApps" | "bouncingLaunch" | "dynamicShadow" | "magnification" => v.is_boolean(),
        "wallpaperIntervalMinutes" => v.as_u64().is_some_and(|minutes| (1..=1440).contains(&minutes)),
        "wallpaperFolders" | "wallpaperFavorites" => v.as_array().is_some_and(|paths| {
            let mut unique = std::collections::HashSet::new();
            paths.len() <= if key == "wallpaperFolders" { 32 } else { 10_000 } && paths.iter().all(|p| p.as_str().is_some_and(|path| path.starts_with('/') && path.len() <= 4096 && !path.contains('\0') && unique.insert(path)))
        }),
        "position" => matches!(v.as_str(), Some("top" | "bottom")),
        "language" => matches!(v.as_str(), Some("vi" | "en")),
        "presets" => v.as_array().is_some_and(|presets| {
            let mut ids = std::collections::HashSet::new();
            let mut names = std::collections::HashSet::new();
            presets.len() <= 32 && presets.iter().all(|preset| {
                preset["id"].as_str().is_some_and(|id| !id.is_empty() && id.len() <= 128 && ids.insert(id))
                    && preset["name"].as_str().is_some_and(|name| !name.trim().is_empty() && name.chars().count() <= 60 && names.insert(name.trim().to_lowercase()))
                    && preset["appearance"].as_object().is_some_and(|fields| {
                        let keys = ["position", "height", "iconSize", "iconSpacing", "opacity", "borderRadius", "accentColor", "bouncingLaunch", "dynamicShadow", "magnification", "maxMagnificationScale", "reduceMotion"];
                        fields.len() == keys.len() && fields.iter().all(|(key,value)| keys.contains(&key.as_str()) && valid_field(key,value))
                    })
            })
        }),
        "monitor" => v.is_null() || v.as_str().is_some_and(|s| !s.is_empty() && s.len() <= 512),
        "iconSize" => v.as_u64().is_some_and(|n| (24..=56).contains(&n)),
        "iconSpacing" => v.as_u64().is_some_and(|n| n <= 24),
        "height" => v.as_u64().is_some_and(|n| (40..=90).contains(&n)),
        "opacity" => v.as_f64().is_some_and(|n| (0.2..=1.0).contains(&n)),
        "borderRadius" => v.as_u64().is_some_and(|n| n <= 40),
        "maxMagnificationScale" => v.as_f64().is_some_and(|n| (1.0..=2.0).contains(&n)),
        "accentColor" => valid_color(v),
        "pinnedApps" => v.as_array().is_some_and(|a| {
            let mut ids = std::collections::HashSet::new();
            let mut desktops = std::collections::HashSet::new();
            a.len() <= 256 && a.iter().all(|p| validate_pin(p) && ids.insert(p["id"].as_str().unwrap())
                && pin_desktop_id(p).is_none_or(|id| desktops.insert(id)))
        }),
        _ => false,
    }
}

/// Strict for incoming changes; forgiving only for migration/load, with a warning.
fn apply_fields(base: &Value, patch: &Value, strict: bool) -> Result<(Value, bool)> {
    let object = patch.as_object().ok_or_else(|| ConfigError::new("invalid_config", "Cấu hình phải là một object JSON"))?;
    let mut next = base.clone();
    let mut repaired = false;
    for (key, value) in object {
        if !strict && key == "pinnedApps" {
            if let Some(pins) = repair_duplicate_desktop_pins(value) {
                next[key] = pins;
                repaired = true;
                continue;
            }
        }
        if !valid_field(key, value) {
            if strict { return Err(ConfigError::new("invalid_config", format!("Giá trị cấu hình không hợp lệ: {key}"))); }
            repaired = true;
            continue;
        }
        next[key] = value.clone();
    }
    Ok((next, repaired))
}

fn persist(path: &Path, snapshot: &Snapshot) -> Result<Option<String>> {
    persist_with_directory_sync(path, snapshot, |parent| fs::File::open(parent)?.sync_all())
}
fn persist_with_directory_sync(path: &Path, snapshot: &Snapshot, sync_directory: impl FnOnce(&Path) -> std::io::Result<()>) -> Result<Option<String>> {
    let parent = path.parent().ok_or_else(|| ConfigError::new("config_path", "Thiếu thư mục cấu hình"))?;
    fs::create_dir_all(parent).map_err(|e| ConfigError::new("config_write", e))?;
    let tmp = path.with_extension(format!("{}.{}.tmp", std::process::id(), snapshot.revision));
    let result = (|| -> std::io::Result<()> {
        let mut file = fs::OpenOptions::new().create_new(true).write(true).mode(0o600).open(&tmp)?;
        file.write_all(&serde_json::to_vec_pretty(snapshot)?)?;
        file.sync_all()?;
        fs::rename(&tmp, path)?;
        Ok(())
    })();
    if result.is_err() { let _ = fs::remove_file(tmp); }
    result.map_err(|e| ConfigError::new("config_write", e))?;
    // Rename has committed: returning a write failure now would retain stale memory
    // while disk already contains the new revision. Surface durability as a warning.
    Ok(sync_directory(parent).err().map(|e| format!("config_durability: {e}")))
}
fn apply_durability_warning(snapshot: &mut Snapshot, warning: Option<String>) {
    if let Some(warning) = warning {
        snapshot.warning = Some(match snapshot.warning.take() { Some(previous) => format!("{previous}\n{warning}"), None => warning });
    }
}

pub struct ConfigStore {
    path: PathBuf,
    pub snapshot: Snapshot,
    pub initialized: bool,
}
impl ConfigStore {
    pub fn load(path: PathBuf) -> Result<Self> {
        let mut store = Self { path, snapshot: Snapshot { schema_version: VERSION, revision: 0, config: defaults(), warning: None }, initialized: false };
        let bytes = match fs::read(&store.path) {
            Ok(b) => b,
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok(store),
            Err(e) => return Err(ConfigError::new("config_read", e)),
        };
        let parsed = serde_json::from_slice::<Snapshot>(&bytes);
        match parsed {
            Ok(mut snapshot) => {
                if snapshot.schema_version > VERSION {
                    return Err(ConfigError::new("config_version", "Cấu hình được tạo bởi phiên bản DeskMorph mới hơn"));
                }
                let original_config = snapshot.config.clone();
                let (config, repaired) = apply_fields(&defaults(), &snapshot.config, false)
                    .unwrap_or_else(|_| (defaults(), true));
                if repaired {
                    store.backup(&bytes)?;
                    snapshot.warning = Some("config_repaired".into());
                }
                snapshot.config = config;
                snapshot.schema_version = VERSION;
                if !repaired && snapshot.config != original_config {
                    let warning = persist(&store.path, &snapshot)?;
                    apply_durability_warning(&mut snapshot, warning);
                }
                store.snapshot = snapshot;
                store.initialized = true;
            }
            Err(_) => {
                store.backup(&bytes)?;
                store.snapshot.warning = Some("config_recovered".into());
                // A damaged native file must not be replaced by an unrelated stale web cache.
                store.initialized = true;
            }
        }
        Ok(store)
    }
    fn backup(&self, bytes: &[u8]) -> Result<()> {
        let stamp = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap_or_default().as_nanos();
        let path = self.path.with_extension(format!("{stamp}.recovery.json"));
        let mut file = fs::OpenOptions::new().create_new(true).write(true).mode(0o600).open(path).map_err(|e| ConfigError::new("config_backup", e))?;
        file.write_all(bytes).and_then(|_| file.sync_all()).map_err(|e| ConfigError::new("config_backup", e))
    }
    pub fn initialize(&mut self, legacy: Option<Value>) -> Result<Snapshot> {
        if !self.initialized {
            let mut next = self.snapshot.clone();
            if let Some(legacy) = legacy {
                match apply_fields(&defaults(), &legacy, false) {
                    Ok((config, repaired)) => {
                        next.config = config;
                        if repaired { next.warning = Some("config_legacy_repaired".into()); }
                    }
                    Err(_) => next.warning = Some("config_legacy_unreadable".into()),
                }
            }
            let warning = persist(&self.path, &next)?;
            apply_durability_warning(&mut next, warning);
            self.snapshot = next;
            self.initialized = true;
        }
        Ok(self.snapshot.clone())
    }
    pub fn patch(&mut self, patch: Value) -> Result<Snapshot> {
        let (config, _) = apply_fields(&self.snapshot.config, &patch, true)?;
        self.commit(config)
    }
    fn replace_document(&mut self, document: &Value, expected_revision: u64) -> Result<Snapshot> {
        if !self.initialized { return Err(ConfigError::new("config_not_ready", "Cấu hình chưa tải xong")); }
        let config = read_document(document)?;
        if self.snapshot.revision != expected_revision { return Err(ConfigError::new("config_conflict", "Cấu hình đã thay đổi; hãy xem lại trước khi áp dụng")); }
        self.commit(config)
    }
    fn commit(&mut self, config: Value) -> Result<Snapshot> {
        let mut next = self.snapshot.clone();
        next.revision = next.revision.checked_add(1).ok_or_else(|| ConfigError::new("config_revision", "Revision overflow"))?;
        next.config = config;
        let warning = persist(&self.path, &next)?;
        apply_durability_warning(&mut next, warning);
        self.snapshot = next.clone();
        self.initialized = true;
        Ok(next)
    }
    fn pin(&mut self, action: &str, id: &str, pin: Option<Value>, target: Option<usize>) -> Result<Snapshot> {
        let mut pins = self.snapshot.config["pinnedApps"].as_array().unwrap().clone();
        let index = pins.iter().position(|p| p["id"].as_str() == Some(id));
        match action {
            "setClasses" => {
                let i = index.ok_or_else(|| ConfigError::new("pin_missing", "Không tìm thấy ứng dụng ghim"))?;
                let classes = pin.as_ref().and_then(|p| p["matchClasses"].as_array())
                    .ok_or_else(|| ConfigError::new("invalid_pin", "Thiếu danh sách WM_CLASS"))?;
                let mut normalized = Vec::new();
                for class in classes {
                    let class = class.as_str().filter(|s| !s.trim().is_empty() && s.len() <= 256 && !s.chars().any(char::is_control))
                        .ok_or_else(|| ConfigError::new("invalid_pin", "WM_CLASS không hợp lệ"))?.trim().to_lowercase();
                    if !normalized.contains(&class) { normalized.push(class); }
                }
                if normalized.len() > 64 || classes.len() > 64 { return Err(ConfigError::new("invalid_pin", "Tối đa 64 WM_CLASS")); }
                for (other_index, other) in pins.iter().enumerate() {
                    if other_index != i && other["matchClasses"].as_array().unwrap().iter().any(|c| normalized.contains(&c.as_str().unwrap().to_lowercase())) {
                        return Err(ConfigError::new("pin_class_conflict", format!("WM_CLASS đã thuộc ứng dụng ghim: {}", other["name"].as_str().unwrap())));
                    }
                }
                pins[i]["matchClasses"] = json!(normalized);
            }
            "remove" => pins.retain(|p| p["id"].as_str() != Some(id)),
            "add" => {
                let pin = pin.filter(|p| validate_pin(p) && p["id"].as_str() == Some(id))
                    .ok_or_else(|| ConfigError::new("invalid_pin", "Ứng dụng ghim không hợp lệ"))?;
                if let Some(i) = index {
                    if pin_desktop_id(&pins[i]) != pin_desktop_id(&pin) {
                        return Err(ConfigError::new("pin_identity_conflict", "ID ghim đã thuộc ứng dụng khác"));
                    }
                    pins[i]["enabled"] = json!(true);
                } else if let Some(i) = pin_desktop_id(&pin).and_then(|desktop| pins.iter().position(|p| pin_desktop_id(p) == Some(desktop))) {
                    pins[i]["enabled"] = json!(true);
                } else { pins.push(pin); }
            }
            "toggleEnabled" => {
                let i = index.ok_or_else(|| ConfigError::new("pin_missing", "Không tìm thấy ứng dụng ghim"))?;
                pins[i]["enabled"] = json!(pins[i]["enabled"].as_bool() == Some(false));
            }
            "move" => {
                let i = index.ok_or_else(|| ConfigError::new("pin_missing", "Không tìm thấy ứng dụng ghim"))?;
                let target = target.ok_or_else(|| ConfigError::new("pin_target", "Thiếu vị trí ghim"))?.min(pins.len() - 1);
                let pin = pins.remove(i);
                pins.insert(target, pin);
            }
            _ => return Err(ConfigError::new("pin_action", "Thao tác ghim không được hỗ trợ")),
        }
        self.patch(json!({"pinnedApps": pins}))
    }
}

pub struct ConfigState(pub Mutex<ConfigStore>);

pub fn publish(app: &AppHandle, snapshot: &Snapshot, previous: Option<&Value>) -> Result<()> {
    // Apply while holding the config lock, preserving native side-effect ordering.
    let c = &snapshot.config;
    let changed = |key: &str| previous.is_none_or(|p| p[key] != c[key]);
    if ["wallpaperScheduleEnabled", "wallpaperIntervalMinutes", "wallpaperFolders", "wallpaperRecursive"].iter().any(|key| changed(key)) {
        super::wallpaper::schedule_changed(app);
    }
    if changed("launcherShortcut") || changed("enabled") {
        super::shortcuts::configure(app, if c["enabled"] == true { c["launcherShortcut"].as_str() } else { None });
    }
    let apply = (|| -> Result<()> {
        super::layout::configure(app, c).map_err(|e| ConfigError::new("layout_config", e))?;
        if c["enabled"] == false && changed("enabled") {
            super::hide_dock_context_menu(app.clone(), None).map_err(|e| ConfigError::new("popup_hide", e))?;
            super::hide_calendar_flyout(app.clone()).map_err(|e| ConfigError::new("popup_hide", e))?;
        }
        let window = app.get_webview_window("taskbar").ok_or_else(|| ConfigError::new("window_missing", "Không tìm thấy Dock"))?;
        if c["enabled"] == true {
            if changed("enabled") || changed("position") || changed("height") || changed("monitor") || changed("autoHide") {
                super::layout::apply(app)
                    .map_err(|e| ConfigError::new("window_position", e))?;
            }
            if changed("enabled") { window.show().map_err(|e| ConfigError::new("window_show", e))?; }
        } else if changed("enabled") { window.hide().map_err(|e| ConfigError::new("window_hide", e))?; }
        Ok(())
    })();
    // Persisted state must reach every UI even if a native window operation fails.
    let broadcast = app.emit("deskmorph:config-snapshot", snapshot).map_err(|e| ConfigError::new("config_event", e));
    apply.and(broadcast).map_err(|mut error| {
        error.message = format!("Đã lưu cấu hình nhưng chưa áp dụng đầy đủ. Thử lại để áp dụng: {}", error.message);
        error.context = Some(json!({"persisted": true, "revision": snapshot.revision}));
        error
    })
}

#[tauri::command]
pub fn get_config(app: AppHandle, state: tauri::State<ConfigState>, legacy: Option<Value>) -> Result<Snapshot> {
    let mut store = state.0.lock().map_err(|e| ConfigError::new("config_lock", e))?;
    let was_initialized = store.initialized;
    let snapshot = store.initialize(legacy)?;
    if !was_initialized { publish(&app, &snapshot, None)?; }
    Ok(snapshot)
}
fn check_retry_revision(expected: Option<u64>, current: u64) -> Result<()> {
    if expected.is_some_and(|revision| revision != current) {
        return Err(ConfigError::new("config_conflict", "Cấu hình đã thay đổi sau thao tác thất bại. Hãy tải lại và kiểm tra trước khi sửa tiếp."));
    }
    Ok(())
}
/// Retry side effects using the latest saved snapshot; do not persist/replay a mutation.
#[tauri::command]
pub fn retry_config_apply(app: AppHandle, state: tauri::State<ConfigState>) -> Result<Snapshot> {
    let store = state.0.lock().map_err(|e| ConfigError::new("config_lock", e))?;
    if !store.initialized { return Err(ConfigError::new("config_not_ready", "Cấu hình chưa tải xong")); }
    let snapshot = store.snapshot.clone();
    publish(&app, &snapshot, None)?;
    Ok(snapshot)
}
#[tauri::command]
pub fn patch_config(app: AppHandle, state: tauri::State<ConfigState>, patch: Value, expected_revision: Option<u64>) -> Result<Snapshot> {
    let mut store = state.0.lock().map_err(|e| ConfigError::new("config_lock", e))?;
    if !store.initialized { return Err(ConfigError::new("config_not_ready", "Cấu hình chưa tải xong; hãy thử lại")); }
    check_retry_revision(expected_revision, store.snapshot.revision)?;
    let previous = store.snapshot.config.clone();
    let snapshot = store.patch(patch)?;
    publish(&app, &snapshot, Some(&previous))?;
    Ok(snapshot)
}
#[tauri::command]
pub fn mutate_pin(app: AppHandle, state: tauri::State<ConfigState>, action: String, id: String, pin: Option<Value>, target: Option<usize>, expected_revision: Option<u64>) -> Result<Snapshot> {
    let mut store = state.0.lock().map_err(|e| ConfigError::new("config_lock", e))?;
    if !store.initialized { return Err(ConfigError::new("config_not_ready", "Cấu hình chưa tải xong; hãy thử lại")); }
    check_retry_revision(expected_revision, store.snapshot.revision)?;
    let previous = store.snapshot.config.clone();
    let snapshot = store.pin(&action, &id, pin, target)?;
    publish(&app, &snapshot, Some(&previous))?;
    Ok(snapshot)
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ImportReview { config: Value, changed_fields: Vec<String>, expected_revision: u64 }
fn read_document(document: &Value) -> Result<Value> {
    let version = document["schemaVersion"].as_u64().ok_or_else(|| ConfigError::new("config_document", "File thiếu schemaVersion"))?;
    if version != u64::from(VERSION) { return Err(ConfigError::new("config_version", "Phiên bản cấu hình không được hỗ trợ")); }
    apply_fields(&defaults(), &document["config"], true).map(|(config, _)| config)
}
#[tauri::command]
pub fn review_config_document(state: tauri::State<ConfigState>, document: Value) -> Result<ImportReview> {
    let config = read_document(&document)?;
    let store = state.0.lock().map_err(|e| ConfigError::new("config_lock", e))?;
    let changed_fields = config.as_object().unwrap().keys().filter(|key| config[*key] != store.snapshot.config[*key]).cloned().collect();
    Ok(ImportReview { config, changed_fields, expected_revision: store.snapshot.revision })
}
#[tauri::command]
pub fn replace_config_document(app: AppHandle, state: tauri::State<ConfigState>, document: Value, expected_revision: u64) -> Result<Snapshot> {
    let mut store = state.0.lock().map_err(|e| ConfigError::new("config_lock", e))?;
    let previous = store.snapshot.config.clone();
    let snapshot = store.replace_document(&document, expected_revision)?;
    publish(&app, &snapshot, Some(&previous))?;
    Ok(snapshot)
}
fn write_export(path: &Path, snapshot: &Snapshot) -> Result<()> {
    use std::os::unix::fs::OpenOptionsExt;
    let stamp = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap_or_default().as_nanos();
    let tmp = path.with_extension(format!("{}.{}.export.tmp", std::process::id(), stamp));
    let bytes = serde_json::to_vec_pretty(&json!({"schemaVersion":VERSION,"config":snapshot.config})).map_err(|e| ConfigError::new("config_export", e))?;
    let result = (|| -> std::io::Result<()> {
        let mut file = fs::OpenOptions::new().create_new(true).write(true).mode(0o600).open(&tmp)?;
        file.write_all(&bytes)?;
        file.sync_all()?;
        fs::rename(&tmp, path)?;
        Ok(())
    })();
    if result.is_err() { let _ = fs::remove_file(tmp); }
    result.map_err(|e| ConfigError::new("config_export", e))
}
#[tauri::command]
pub fn export_config(window: tauri::WebviewWindow, state: tauri::State<ConfigState>) -> Result<Option<String>> {
    use gtk::prelude::*;
    let snapshot = state.0.lock().map_err(|e| ConfigError::new("config_lock", e))?.snapshot.clone();
    let language = snapshot.config["language"].as_str().unwrap_or("vi");
    let label = |key| crate::ui_messages::text(language, key);
    let parent = window.gtk_window().map_err(|e| ConfigError::new("config_export", e))?;
    let dialog = gtk::FileChooserDialog::new(Some(label("exportConfig")), Some(&parent), gtk::FileChooserAction::Save);
    dialog.add_buttons(&[(label("cancel"), gtk::ResponseType::Cancel), (label("save"), gtk::ResponseType::Accept)]);
    dialog.set_current_name("deskmorph-config.json");
    dialog.set_do_overwrite_confirmation(true);
    let response = dialog.run();
    let path = if response == gtk::ResponseType::Accept { dialog.filename() } else { None };
    dialog.close();
    if let Some(path) = path {
        let active_path = state.0.lock().map_err(|e| ConfigError::new("config_lock", e))?.path.clone();
        if path.canonicalize().ok().zip(active_path.canonicalize().ok()).is_some_and(|(chosen, active)| chosen == active) {
            return Err(ConfigError::new("config_export", "Hãy chọn file khác với file cấu hình đang được ứng dụng sử dụng"));
        }
        write_export(&path, &snapshot)?;
        return Ok(Some(path.to_string_lossy().into_owned()));
    }
    Ok(None)
}

#[cfg(test)]
mod tests {
    use super::*;
    fn path() -> PathBuf {
        let stamp = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos();
        std::env::temp_dir().join(format!("deskmorph-config-{}-{stamp}", std::process::id())).join("config.json")
    }
    #[test]
    fn retry_rejects_newer_config_instead_of_replaying_a_stale_mutation() {
        assert!(check_retry_revision(None, 5).is_ok());
        assert!(check_retry_revision(Some(5), 5).is_ok());
        assert_eq!(check_retry_revision(Some(4), 5).unwrap_err().code, "config_conflict");
    }
    #[test]
    fn shortcut_is_opt_in_validated_persisted_and_can_be_disabled() {
        let path = path();
        let mut store = ConfigStore::load(path.clone()).unwrap();
        assert!(store.initialize(None).unwrap().config["launcherShortcut"].is_null());
        store.patch(json!({"launcherShortcut": "Ctrl+Super+K"})).unwrap();
        let bytes = fs::read(&path).unwrap();
        for invalid in [json!("L"), json!("Shift+L"), json!("Ctrl+Ctrl+L"), json!(42), json!(true)] {
            assert!(store.patch(json!({"launcherShortcut": invalid})).is_err());
            assert_eq!(fs::read(&path).unwrap(), bytes);
        }
        let mut loaded = ConfigStore::load(path.clone()).unwrap();
        assert_eq!(loaded.snapshot.config["launcherShortcut"], "Ctrl+Super+K");
        loaded.patch(json!({"launcherShortcut": null})).unwrap();
        assert!(ConfigStore::load(path.clone()).unwrap().snapshot.config["launcherShortcut"].is_null());
        fs::remove_dir_all(path.parent().unwrap()).unwrap();
    }
    #[test]
    fn migration_defaults_and_restart() {
        use std::os::unix::fs::PermissionsExt;
        let path = path();
        let mut store = ConfigStore::load(path.clone()).unwrap();
        let snapshot = store.initialize(Some(json!({"enabled": false, "autoHide": true, "height": 999}))).unwrap();
        assert_eq!(fs::metadata(&path).unwrap().permissions().mode() & 0o777, 0o600);
        assert_eq!(snapshot.config["enabled"], false);
        assert_eq!(snapshot.config["autoHide"], true);
        assert_eq!(snapshot.config["height"], 52);
        assert_eq!(snapshot.warning.as_deref(), Some("config_legacy_repaired"));
        let mut loaded = ConfigStore::load(path.clone()).unwrap();
        assert_eq!(loaded.initialize(Some(json!({"enabled":true}))).unwrap().config, snapshot.config);
        fs::remove_dir_all(path.parent().unwrap()).unwrap();
    }
    #[test]
    fn post_rename_sync_failure_reports_committed_data_with_durability_warning() {
        let path = path();
        let snapshot = Snapshot { schema_version: VERSION, revision: 7, config: defaults(), warning: None };
        let warning = persist_with_directory_sync(&path, &snapshot, |_| Err(std::io::Error::other("injected directory sync failure"))).unwrap();
        assert_eq!(warning.as_deref(), Some("config_durability: injected directory sync failure"));
        let disk: Snapshot = serde_json::from_slice(&fs::read(&path).unwrap()).unwrap();
        assert_eq!(disk.revision, 7); assert_eq!(disk.config, snapshot.config);
        let mut memory = snapshot; apply_durability_warning(&mut memory, warning);
        assert_eq!(memory.revision, disk.revision); assert_eq!(memory.config, disk.config); assert!(memory.warning.is_some());
        assert_eq!(fs::read_dir(path.parent().unwrap()).unwrap().count(), 1);
        fs::remove_dir_all(path.parent().unwrap()).unwrap();
    }
    #[test]
    fn invalid_patch_and_io_failure_leave_memory_unchanged() {
        let path = path();
        let mut store = ConfigStore::load(path.clone()).unwrap();
        store.initialize(None).unwrap();
        let original = store.snapshot.clone();
        for patch in [json!({"height": "52"}), json!({"accentColor":"bad"}), json!({"opacity": 2}), json!({"pinnedApps":[{}]}), json!({"unknown":true}), json!({"wallpaperIntervalMinutes":0}), json!({"wallpaperIntervalMinutes":1.5}), json!({"wallpaperIntervalMinutes":1441})] {
            assert!(store.patch(patch).is_err());
        }
        store.path = path.join("not-a-directory");
        assert!(store.patch(json!({"enabled":false})).is_err());
        assert_eq!(store.snapshot.config, original.config);
        assert_eq!(store.snapshot.revision, original.revision);
        fs::remove_dir_all(path.parent().unwrap()).unwrap();
    }
    #[test]
    fn corrupt_file_is_backed_up_and_future_version_is_not_overwritten() {
        let path = path();
        fs::create_dir_all(path.parent().unwrap()).unwrap();
        fs::write(&path, b"broken").unwrap();
        let mut store = ConfigStore::load(path.clone()).unwrap();
        assert!(store.snapshot.warning.is_some());
        assert_eq!(fs::read(&path).unwrap(), b"broken");
        assert_eq!(fs::read_dir(path.parent().unwrap()).unwrap().count(), 2);
        store.patch(json!({"enabled":false})).unwrap();
        let future = Snapshot { schema_version: VERSION + 1, ..store.snapshot };
        fs::write(&path, serde_json::to_vec(&future).unwrap()).unwrap();
        assert_eq!(ConfigStore::load(path.clone()).err().unwrap().code, "config_version");
        fs::remove_dir_all(path.parent().unwrap()).unwrap();
    }
    #[test]
    fn import_rejects_invalid_version_and_preset_data() {
        assert!(read_document(&json!({"schemaVersion":2,"config":defaults()})).is_err());
        assert!(read_document(&json!({"schemaVersion":1,"config":{"height":1000}})).is_err());
        assert!(read_document(&json!({"schemaVersion":1,"config":{"presets":[{"id":"x","name":"x","appearance":{"height":52}}]}})).is_err());
        let valid = read_document(&json!({"schemaVersion":1,"config":{"height":64,"autoHide":true}})).unwrap();
        assert_eq!(valid["height"], 64);
        assert_eq!(valid["autoHide"], true);
        assert_eq!(valid["language"], "vi");
    }
    #[test]
    fn additive_defaults_are_persisted_when_loading_an_older_valid_snapshot() {
        let path = path(); fs::create_dir_all(path.parent().unwrap()).unwrap();
        let mut config = defaults(); config.as_object_mut().unwrap().remove("wallpaperFolders");
        let snapshot = Snapshot { schema_version: VERSION, revision: 3, config, warning: None };
        fs::write(&path, serde_json::to_vec(&snapshot).unwrap()).unwrap();
        let loaded = ConfigStore::load(path.clone()).unwrap();
        let persisted: Snapshot = serde_json::from_slice(&fs::read(&path).unwrap()).unwrap();
        assert_eq!(persisted.config, loaded.snapshot.config); assert_eq!(persisted.config["wallpaperFolders"], json!([]));
        assert_eq!(persisted.revision, 3);
        fs::remove_dir_all(path.parent().unwrap()).unwrap();
    }
    #[test]
    fn import_is_transactional_and_rejects_stale_review() {
        let path = path();
        let mut store = ConfigStore::load(path.clone()).unwrap();
        let document = json!({"schemaVersion":1,"config":{"height":64}});
        assert_eq!(store.replace_document(&document, 0).unwrap_err().code, "config_not_ready");
        store.initialize(None).unwrap();
        let reviewed_revision = store.snapshot.revision;
        store.patch(json!({"autoHide":true})).unwrap();
        let before = store.snapshot.clone();
        let bytes = fs::read(&path).unwrap();
        assert_eq!(store.replace_document(&document, reviewed_revision).unwrap_err().code, "config_conflict");
        assert!(store.replace_document(&json!({"schemaVersion":1,"config":{"height":1000}}), before.revision).is_err());
        assert_eq!(store.snapshot.config, before.config);
        assert_eq!(store.snapshot.revision, before.revision);
        assert_eq!(fs::read(&path).unwrap(), bytes);
        let imported = store.replace_document(&document, before.revision).unwrap();
        assert_eq!(imported.config["height"], 64);
        assert_eq!(imported.revision, before.revision + 1);
        assert_eq!(ConfigStore::load(path.clone()).unwrap().snapshot.config, imported.config);
        fs::remove_dir_all(path.parent().unwrap()).unwrap();
    }
    #[test]
    fn export_round_trips_and_failure_preserves_destination() {
        let path = path();
        fs::create_dir_all(path.parent().unwrap()).unwrap();
        let snapshot = Snapshot { schema_version: VERSION, revision: 7, config: defaults(), warning: None };
        write_export(&path, &snapshot).unwrap();
        let document: Value = serde_json::from_slice(&fs::read(&path).unwrap()).unwrap();
        assert_eq!(read_document(&document).unwrap(), snapshot.config);
        assert!(document.get("revision").is_none());
        let directory = path.with_extension("directory");
        fs::create_dir(&directory).unwrap();
        fs::write(directory.join("keep"), "original").unwrap();
        assert!(write_export(&directory, &snapshot).is_err());
        assert_eq!(fs::read_to_string(directory.join("keep")).unwrap(), "original");
        assert_eq!(fs::read_dir(path.parent().unwrap()).unwrap().count(), 2, "temporary export files must be cleaned up");
        fs::remove_dir_all(path.parent().unwrap()).unwrap();
    }
    #[test]
    fn semantically_corrupt_snapshot_recovers_without_losing_original() {
        let path = path();
        fs::create_dir_all(path.parent().unwrap()).unwrap();
        let broken = Snapshot { schema_version: 1, revision: 10, config: json!([]), warning: None };
        let bytes = serde_json::to_vec(&broken).unwrap();
        fs::write(&path, &bytes).unwrap();
        let store = ConfigStore::load(path.clone()).unwrap();
        assert_eq!(store.snapshot.config, defaults());
        assert!(store.snapshot.warning.is_some());
        assert_eq!(fs::read(&path).unwrap(), bytes);
        assert_eq!(fs::read_dir(path.parent().unwrap()).unwrap().count(), 2);
        fs::remove_dir_all(path.parent().unwrap()).unwrap();
    }
    #[test]
    fn class_mapping_is_atomic_validated_and_persistent() {
        let path = path();
        let mut store = ConfigStore::load(path.clone()).unwrap();
        let original = store.snapshot.config.clone();
        store.pin("setClasses", "code", Some(json!({"matchClasses":[" DecodeTool ","decodetool"]})), None).unwrap();
        let pin = store.snapshot.config["pinnedApps"].as_array().unwrap().iter().find(|p| p["id"] == "code").unwrap();
        assert_eq!(pin["matchClasses"], json!(["decodetool"]));
        assert_eq!(pin["command"], original["pinnedApps"].as_array().unwrap().iter().find(|p| p["id"] == "code").unwrap()["command"]);
        let saved = store.snapshot.config.clone();
        for (id, classes) in [("files", json!(["DECodetool"])), ("code", json!([" "])), ("code", json!(["bad\nclass"])), ("missing", json!([])), ("code", json!(vec!["x"; 65]))] {
            assert!(store.pin("setClasses", id, Some(json!({"matchClasses":classes})), None).is_err());
            assert_eq!(store.snapshot.config, saved);
        }
        assert_eq!(ConfigStore::load(path.clone()).unwrap().snapshot.config, saved);
        store.pin("setClasses", "code", Some(json!({"matchClasses":[]})), None).unwrap();
        fs::remove_dir_all(path.parent().unwrap()).unwrap();
    }
    #[test]
    fn desktop_pin_identity_is_unique_across_add_import_and_restart() {
        let path = path();
        let mut store = ConfigStore::load(path.clone()).unwrap();
        let old = json!({"id":"legacy", "name":"My legacy name", "command":"desktop:sample.desktop", "matchClasses":["sample"], "iconType":"custom", "enabled":false});
        let fresh = json!({"id":"sample.desktop", "desktopId":"sample.desktop", "name":"Catalogue name", "command":"desktop:sample.desktop", "matchClasses":["sample"], "iconType":"custom", "enabled":true});
        store.initialize(Some(json!({"pinnedApps":[old.clone()]}))).unwrap();
        store.pin("add", "sample.desktop", Some(fresh.clone()), None).unwrap();
        let mut enabled = old.clone(); enabled["enabled"] = json!(true);
        assert_eq!(store.snapshot.config["pinnedApps"], json!([enabled.clone()]));
        store.pin("add", "sample.desktop", Some(fresh.clone()), None).unwrap();
        assert_eq!(store.snapshot.config["pinnedApps"], json!([enabled.clone()]));
        assert_eq!(ConfigStore::load(path.clone()).unwrap().snapshot.config["pinnedApps"], json!([enabled.clone()]));
        let before = store.snapshot.clone();
        assert!(store.patch(json!({"pinnedApps":[enabled.clone(), fresh.clone()]})).is_err());
        assert!(read_document(&json!({"schemaVersion":1,"config":{"pinnedApps":[enabled.clone(),fresh]}})).is_err());
        let conflict = json!({"id":"legacy", "desktopId":"other.desktop", "name":"Other", "command":"desktop:other.desktop", "matchClasses":[], "iconType":"custom"});
        assert_eq!(store.pin("add", "legacy", Some(conflict), None).unwrap_err().code, "pin_identity_conflict");
        assert_eq!(store.snapshot.config, before.config);
        assert_eq!(store.snapshot.revision, before.revision);
        store.pin("remove", "legacy", None, None).unwrap();
        assert_eq!(store.snapshot.config["pinnedApps"], json!([]));
        fs::remove_dir_all(path.parent().unwrap()).unwrap();
    }
    #[test]
    fn duplicate_desktop_pin_migration_keeps_order_metadata_and_original_document() {
        let path = path();
        let mut store = ConfigStore::load(path.clone()).unwrap();
        let first = json!({"id":"old", "name":"Keep me", "command":"sample.desktop", "matchClasses":[], "iconType":"custom", "enabled":false});
        let duplicate = json!({"id":"new", "desktopId":"sample.desktop", "name":"Duplicate", "command":"desktop:sample.desktop", "matchClasses":[], "iconType":"custom"});
        let custom = json!({"id":"custom", "name":"Custom profile", "command":"editor --profile work", "matchClasses":[], "iconType":"custom"});
        let original = json!({"pinnedApps":[first.clone(), custom.clone(), duplicate]});
        let migrated = store.initialize(Some(original.clone())).unwrap();
        let mut expected = first; expected["enabled"] = json!(true);
        assert_eq!(migrated.config["pinnedApps"], json!([expected.clone(), custom.clone()]));
        assert!(migrated.warning.is_some());
        let disk = Snapshot { schema_version:1, revision:42, config:original, warning:None };
        let bytes = serde_json::to_vec(&disk).unwrap(); fs::write(&path, &bytes).unwrap();
        let loaded = ConfigStore::load(path.clone()).unwrap();
        assert_eq!(loaded.snapshot.config["pinnedApps"], json!([expected, custom]));
        assert_eq!(loaded.snapshot.revision, 42);
        assert!(loaded.snapshot.warning.is_some());
        assert_eq!(fs::read(&path).unwrap(), bytes);
        assert!(fs::read_dir(path.parent().unwrap()).unwrap().filter_map(|e| e.ok()).any(|e| e.path().to_string_lossy().ends_with(".recovery.json") && fs::read(e.path()).unwrap() == bytes));
        fs::remove_dir_all(path.parent().unwrap()).unwrap();
    }
    #[test]
    fn concurrent_disjoint_changes_and_pin_actions_preserve_other_updates() {
        let path = path();
        let store = std::sync::Arc::new(Mutex::new(ConfigStore::load(path.clone()).unwrap()));
        let a = store.clone();
        let b = store.clone();
        let t1 = std::thread::spawn(move || a.lock().unwrap().patch(json!({"height":60})).unwrap());
        let t2 = std::thread::spawn(move || b.lock().unwrap().patch(json!({"autoHide":true})).unwrap());
        t1.join().unwrap(); t2.join().unwrap();
        let mut store = store.lock().unwrap();
        store.pin("remove", "chrome", None, None).unwrap();
        store.pin("move", "files", None, Some(0)).unwrap();
        assert_eq!(store.snapshot.config["height"], 60);
        assert_eq!(store.snapshot.config["autoHide"], true);
        assert_eq!(store.snapshot.config["pinnedApps"][0]["id"], "files");
        assert_eq!(store.snapshot.revision, 4);
        fs::remove_dir_all(path.parent().unwrap()).unwrap();
    }
}
