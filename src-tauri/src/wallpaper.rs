//! Bounded wallpaper scanning and thumbnail generation, off the UI thread.
use gtk::gdk_pixbuf::Pixbuf;
use serde::Serialize;
use std::{collections::{HashSet, hash_map::DefaultHasher}, fs, hash::{Hash, Hasher}, path::{Path, PathBuf}, sync::{Arc, Mutex, atomic::{AtomicBool, AtomicU64, Ordering}}, time::UNIX_EPOCH};
use tauri::{AppHandle, Manager};

const MAX_VISITED: usize = 20_000;
const MAX_IMAGES: usize = 5_000;
const MAX_FILE_BYTES: u64 = 128 * 1024 * 1024;
#[derive(Clone, Serialize, Debug)]
#[serde(rename_all = "camelCase")]
pub struct Image {
    pub path: String, pub filename: String, pub folder: String, pub format: String,
}
#[derive(Serialize, Debug)]
pub struct Issue { path: String, message: String }
#[derive(Serialize, Debug)]
#[serde(rename_all = "camelCase")]
pub struct Scan { pub images: Vec<Image>, issues: Vec<Issue>, limited: bool }
#[derive(Default)]
pub struct Library {
    generation: AtomicU64, active: Mutex<Option<String>>, worker: Mutex<()>,
    known: Mutex<HashSet<PathBuf>>, thumbnails: Mutex<()>,
    apply: Mutex<()>, scheduler: Scheduler,
}
#[derive(Default)]
pub struct WallpaperState(pub Arc<Library>);
impl Library {
    fn begin_scan(&self, request_id: String) -> Result<u64, String> {
        let mut active = self.active.lock().map_err(|e| e.to_string())?;
        *active = Some(request_id);
        Ok(self.generation.fetch_add(1, Ordering::SeqCst) + 1)
    }
    fn cancel_scan(&self, request_id: &str) -> Result<(), String> {
        let mut active = self.active.lock().map_err(|e| e.to_string())?;
        if active.as_deref() == Some(request_id) {
            *active = None;
            self.generation.fetch_add(1, Ordering::SeqCst);
        }
        Ok(())
    }
    fn scan(&self, generation: u64, folders: Vec<PathBuf>, recursive: bool) -> Result<Scan, String> {
        let _worker = self.worker.lock().map_err(|e| e.to_string())?;
        let cancelled = || self.generation.load(Ordering::SeqCst) != generation;
        let scan = scan_paths(folders, recursive, cancelled)?;
        // Publication and cancellation share the same lock: a cancelled scan
        // must not replace the thumbnail allowlist after the final check.
        let _active = self.active.lock().map_err(|e| e.to_string())?;
        if cancelled() { return Err("wallpaper_scan_cancelled".into()); }
        *self.known.lock().map_err(|e| e.to_string())? = scan.images.iter().map(|image| PathBuf::from(&image.path)).collect();
        Ok(scan)
    }
}
fn issue(issues: &mut Vec<Issue>, path: &Path, message: impl ToString) {
    if issues.len() < 100 { issues.push(Issue { path: path.to_string_lossy().into_owned(), message: message.to_string() }); }
}
pub fn default_folders() -> Vec<PathBuf> {
    let mut paths = vec![PathBuf::from("/usr/share/backgrounds"), PathBuf::from("/usr/share/backgrounds/pop")];
    if let Some(home) = std::env::var_os("HOME") { paths.extend([PathBuf::from(&home).join("Pictures"), PathBuf::from(&home).join("Pictures/Wallpapers"), PathBuf::from(home).join(".local/share/backgrounds")]); }
    paths
}
pub fn configured_folders(config: &serde_json::Value) -> Vec<PathBuf> {
    let selected: Vec<_> = config["wallpaperFolders"].as_array().into_iter().flatten().filter_map(|v| v.as_str().map(PathBuf::from)).collect();
    if selected.is_empty() { default_folders() } else { selected }
}
fn image_info(path: &Path) -> Result<(), String> {
    let metadata = fs::metadata(path).map_err(|e| e.to_string())?;
    if !metadata.is_file() || metadata.len() > MAX_FILE_BYTES { return Err("Image exceeds the 128 MB file limit".into()); }
    let (_, width, height) = Pixbuf::file_info(path).ok_or("Unsupported or damaged image")?;
    if width <= 0 || height <= 0 || i64::from(width) * i64::from(height) > 100_000_000 { return Err("Image exceeds the 100 megapixel limit".into()); }
    Ok(())
}
pub fn scan_paths(folders: Vec<PathBuf>, recursive: bool, cancelled: impl Fn() -> bool) -> Result<Scan, String> {
    let mut scan = Scan { images: Vec::new(), issues: Vec::new(), limited: false };
    let mut pending = folders;
    let mut directories = HashSet::new();
    let mut images = HashSet::new();
    let mut visited = 0;
    while let Some(directory) = pending.pop() {
        if cancelled() { return Err("wallpaper_scan_cancelled".into()); }
        let directory = match directory.canonicalize() { Ok(path) => path, Err(e) => { issue(&mut scan.issues, &directory, e); continue; } };
        if !directories.insert(directory.clone()) { continue; }
        let entries = match fs::read_dir(&directory) { Ok(entries) => entries, Err(e) => { issue(&mut scan.issues, &directory, e); continue; } };
        for entry in entries {
            if cancelled() { return Err("wallpaper_scan_cancelled".into()); }
            visited += 1;
            if visited > MAX_VISITED || scan.images.len() >= MAX_IMAGES { scan.limited = true; break; }
            let entry = match entry { Ok(entry) => entry, Err(e) => { issue(&mut scan.issues, &directory, e); continue; } };
            let path = entry.path();
            let kind = match entry.file_type() { Ok(kind) => kind, Err(e) => { issue(&mut scan.issues, &path, e); continue; } };
            // Never traverse directory symlinks; canonical roots may be explicitly selected.
            if kind.is_dir() { if recursive { pending.push(path); } continue; }
            if !kind.is_file() && !kind.is_symlink() { continue; }
            let format = path.extension().and_then(|s| s.to_str()).unwrap_or("").to_ascii_lowercase();
            if !matches!(format.as_str(), "jpg" | "jpeg" | "png" | "webp" | "bmp") { continue; }
            let canonical = match path.canonicalize() { Ok(path) => path, Err(e) => { issue(&mut scan.issues, &path, e); continue; } };
            if !images.insert(canonical.clone()) { continue; }
            if let Err(e) = image_info(&canonical) { issue(&mut scan.issues, &path, e); continue; }
            scan.images.push(Image {
                filename: canonical.file_name().unwrap_or_default().to_string_lossy().into_owned(),
                folder: canonical.parent().unwrap_or(Path::new("/")).to_string_lossy().into_owned(),
                path: canonical.to_string_lossy().into_owned(), format,
            });
        }
        if scan.limited { break; }
    }
    scan.images.sort_by(|a,b| a.path.cmp(&b.path));
    Ok(scan)
}
#[tauri::command]
pub async fn scan_wallpapers(app: AppHandle, state: tauri::State<'_, WallpaperState>, request_id: String) -> Result<Scan, String> {
    if request_id.len() > 128 { return Err("invalid_scan_id".into()); }
    let library = state.0.clone();
    let generation = library.begin_scan(request_id)?;
    let config = app.state::<crate::config::ConfigState>().0.lock().map_err(|e| e.to_string())?.snapshot.config.clone();
    tauri::async_runtime::spawn_blocking(move || {
        library.scan(generation, configured_folders(&config), config["wallpaperRecursive"] == true)
    }).await.map_err(|e| e.to_string())?
}
#[tauri::command]
pub fn cancel_wallpaper_scan(state: tauri::State<WallpaperState>, request_id: String) -> Result<(), String> {
    state.0.cancel_scan(&request_id)
}
#[derive(Serialize)]
pub struct Thumbnail { path: String, thumbnail: Option<String>, error: Option<String> }
fn thumbnail_path(path: &Path, cache: &Path) -> Result<PathBuf, String> {
    let metadata = fs::metadata(path).map_err(|e| e.to_string())?;
    let mut hash = DefaultHasher::new();
    path.hash(&mut hash); metadata.len().hash(&mut hash);
    metadata.modified().map_err(|e| e.to_string())?.duration_since(UNIX_EPOCH).map_err(|e| e.to_string())?.as_nanos().hash(&mut hash);
    Ok(cache.join(format!("{:016x}.png", hash.finish())))
}
fn make_thumbnail(path: &Path, cache: &Path) -> Result<PathBuf, String> {
    let target = thumbnail_path(path, cache)?;
    if target.is_file() { return Ok(target); }
    image_info(path)?;
    let image = Pixbuf::from_file_at_scale(path, 320, 200, true).map_err(|e| e.to_string())?;
    let image = image.apply_embedded_orientation().unwrap_or(image);
    let temporary = target.with_extension("tmp");
    let result = image.savev(&temporary, "png", &[]).map_err(|e| e.to_string()).and_then(|_| fs::rename(&temporary, &target).map_err(|e| e.to_string()));
    if result.is_err() { let _ = fs::remove_file(&temporary); }
    result?;
    Ok(target)
}
fn trim_cache(cache: &Path) {
    let mut files: Vec<_> = fs::read_dir(cache).into_iter().flatten().flatten().filter_map(|entry| {
        let metadata = entry.metadata().ok()?;
        if !metadata.is_file() { return None; }
        Some((entry.path(), metadata.modified().ok()?, metadata.len()))
    }).collect();
    files.sort_by_key(|file| file.1);
    let mut total: u64 = files.iter().map(|file| file.2).sum();
    let mut count = files.len();
    for (path, _, size) in files {
        if count <= 512 && total <= 64 * 1024 * 1024 { break; }
        if fs::remove_file(path).is_ok() { count -= 1; total = total.saturating_sub(size); }
    }
}
#[tauri::command]
pub async fn wallpaper_thumbnails(app: AppHandle, state: tauri::State<'_, WallpaperState>, paths: Vec<String>) -> Result<Vec<Thumbnail>, String> {
    if paths.len() > 48 { return Err("A thumbnail page may contain at most 48 images".into()); }
    let library = state.0.clone();
    let cache = app.path().app_cache_dir().map_err(|e| e.to_string())?.join("wallpaper-thumbnails-v1");
    tauri::async_runtime::spawn_blocking(move || {
        let _worker = library.thumbnails.lock().map_err(|e| e.to_string())?;
        fs::create_dir_all(&cache).map_err(|e| e.to_string())?;
        let mut result = Vec::new();
        for path in paths {
            let permitted = library.known.lock().map_err(|e| e.to_string())?.contains(Path::new(&path));
            let thumbnail = if permitted { make_thumbnail(Path::new(&path), &cache) } else { Err("Image is not in the scanned library".into()) };
            result.push(match thumbnail {
                Ok(target) => {
                    app.asset_protocol_scope().allow_file(&target).map_err(|e| e.to_string())?;
                    Thumbnail { path, thumbnail: Some(target.to_string_lossy().into_owned()), error: None }
                },
                Err(error) => Thumbnail { path, thumbnail: None, error: Some(error) },
            });
        }
        trim_cache(&cache);
        Ok(result)
    }).await.map_err(|e| e.to_string())?
}

#[cfg(test)]
mod tests {
    use super::*;
    fn fixture() -> PathBuf {
        let path = std::env::temp_dir().join(format!("deskmorph-wallpaper-{}-{}", std::process::id(), std::time::SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos()));
        fs::create_dir_all(path.join("nested")).unwrap(); path
    }
    fn image(path: &Path, width: i32) {
        let pixbuf = Pixbuf::new(gtk::gdk_pixbuf::Colorspace::Rgb, false, 8, width, 16).unwrap();
        pixbuf.fill(0x48b9c7ff); pixbuf.savev(path, "png", &[]).unwrap();
    }
    #[test]
    fn recursive_scan_deduplicates_roots_skips_symlink_loops_and_reports_bad_files() {
        let path = fixture(); image(&path.join("one.png"), 32); image(&path.join("nested/two.png"), 64);
        fs::write(path.join("broken.png"), "not an image").unwrap();
        std::os::unix::fs::symlink(&path, path.join("nested/loop")).unwrap();
        std::os::unix::fs::symlink(path.join("one.png"), path.join("duplicate.png")).unwrap();
        let scan = scan_paths(vec![path.clone(), path.join("nested"), path.join("missing")], true, || false).unwrap();
        assert_eq!(scan.images.len(), 2); assert_eq!(scan.issues.len(), 2); assert!(!scan.limited);
        assert_eq!(scan_paths(vec![path.clone()], false, || false).unwrap().images.len(), 1);
        assert_eq!(scan_paths(vec![path.clone()], true, || true).unwrap_err(), "wallpaper_scan_cancelled");
        fs::remove_dir_all(path).unwrap();
    }
    #[test]
    fn shuffle_handles_empty_single_and_excludes_current_from_multiple_images() {
        let item = |path: &str| Image { path: path.into(), filename: path.into(), folder: "/".into(), format: "png".into() };
        assert!(choose_image(&[], "").is_none());
        let single = [item("one")]; assert_eq!(choose_image(&single, "one").unwrap().path, "one");
        let multiple = [item("one"), item("two")];
        for _ in 0..20 { assert_eq!(choose_image(&multiple, "one").unwrap().path, "two"); }
    }
    #[test]
    fn schedule_handles_disable_config_changes_sleep_and_clock_adjustments() {
        let mut clock = ScheduleClock::default();
        assert!(!clock.tick("disabled".into(), None, 0)); assert_eq!(clock.due, None);
        assert!(!clock.tick("enabled".into(), Some(60_000), 1_000)); assert_eq!(clock.due, Some(61_000));
        assert!(!clock.tick("enabled".into(), Some(60_000), 60_999));
        assert!(clock.tick("enabled".into(), Some(60_000), 61_000));
        assert!(!clock.tick("enabled".into(), Some(60_000), 61_000), "no duplicate attempt at the same deadline");
        assert!(clock.tick("enabled".into(), Some(60_000), 600_000), "resume after missed cycles makes one attempt");
        clock.finish(603_000); assert_eq!(clock.due, Some(663_000));
        assert!(!clock.tick("enabled".into(), Some(60_000), 603_000));
        assert!(!clock.tick("enabled".into(), Some(60_000), 500_000), "backwards clock jump resets deadline");
        assert_eq!(clock.due, Some(560_000));
        assert!(!clock.tick("new-folders".into(), Some(60_000), 520_000)); assert_eq!(clock.due, Some(580_000));
        assert!(!clock.tick("disabled".into(), None, 581_000)); assert_eq!(clock.due, None);
    }
    #[test]
    fn scan_limits_entries_and_refreshes_deleted_images() {
        let path = fixture(); image(&path.join("one.png"), 32);
        assert_eq!(scan_paths(vec![path.clone()], true, || false).unwrap().images.len(), 1);
        fs::remove_file(path.join("one.png")).unwrap();
        assert!(scan_paths(vec![path.clone()], true, || false).unwrap().images.is_empty());
        for index in 0..=MAX_VISITED { fs::write(path.join(format!("entry-{index}.txt")), "").unwrap(); }
        let scan = scan_paths(vec![path.clone()], true, || false).unwrap();
        assert!(scan.limited); assert!(scan.images.is_empty());
        fs::remove_dir_all(path).unwrap();
    }
    #[test]
    fn scan_reports_permissions_and_bounds_images_files_and_issues() {
        use std::os::unix::fs::PermissionsExt;
        let path = fixture();
        let denied = path.join("denied"); fs::create_dir(&denied).unwrap();
        image(&denied.join("private.png"), 16);
        image(&path.join("readable.png"), 16);
        fs::set_permissions(&denied, fs::Permissions::from_mode(0o000)).unwrap();
        let denied_result = fs::read_dir(&denied);
        let scan = scan_paths(vec![path.clone()], true, || false).unwrap();
        // Restore even before assertions, so failure never leaves an unreadable fixture.
        fs::set_permissions(&denied, fs::Permissions::from_mode(0o700)).unwrap();
        assert!(denied_result.is_err(), "Run permission fixtures as an unprivileged user");
        assert_eq!(scan.images.len(), 1);
        assert_eq!(scan.issues.len(), 1); assert_eq!(scan.issues[0].path, denied.to_string_lossy());
        fs::remove_dir_all(&denied).unwrap();
        let too_large = path.join("oversized.png");
        fs::File::create(&too_large).unwrap().set_len(MAX_FILE_BYTES + 1).unwrap();
        let scan = scan_paths(vec![path.clone()], true, || false).unwrap();
        assert_eq!(scan.images.len(), 1);
        assert!(scan.issues.iter().any(|issue| issue.message.contains("128 MB")));
        fs::remove_file(too_large).unwrap();
        // Keep the original small PNG payload, but give it a valid oversized
        // IHDR/CRC. Metadata validation must reject it before full decode.
        let oversized_dimensions = path.join("dimensions.png");
        let mut png = fs::read(path.join("readable.png")).unwrap();
        assert_eq!(&png[12..16], b"IHDR");
        png[16..20].copy_from_slice(&10_001u32.to_be_bytes());
        png[20..24].copy_from_slice(&10_000u32.to_be_bytes());
        let mut crc = !0u32;
        for byte in &png[12..29] {
            crc ^= u32::from(*byte);
            for _ in 0..8 { crc = (crc >> 1) ^ if crc & 1 != 0 { 0xedb88320 } else { 0 }; }
        }
        png[29..33].copy_from_slice(&(!crc).to_be_bytes());
        fs::write(&oversized_dimensions, png).unwrap();
        assert!(image_info(&oversized_dimensions).unwrap_err().contains("100 megapixel"));
        fs::remove_file(oversized_dimensions).unwrap();
        for index in 0..150 { fs::write(path.join(format!("corrupt-{index}.png")), "invalid").unwrap(); }
        let scan = scan_paths(vec![path.clone()], true, || false).unwrap();
        assert_eq!(scan.images.len(), 1); assert_eq!(scan.issues.len(), 100);
        for index in 0..150 { fs::remove_file(path.join(format!("corrupt-{index}.png"))).unwrap(); }
        let bytes = fs::read(path.join("readable.png")).unwrap();
        for index in 0..MAX_IMAGES { fs::write(path.join(format!("valid-{index}.png")), &bytes).unwrap(); }
        let scan = scan_paths(vec![path.clone()], true, || false).unwrap();
        assert_eq!(scan.images.len(), MAX_IMAGES); assert!(scan.limited);
        fs::remove_dir_all(path).unwrap();
    }
    #[test]
    fn scan_cancels_during_traversal_and_superseded_requests_cannot_publish() {
        let path = fixture(); image(&path.join("one.png"), 16);
        for index in 0..128 { fs::write(path.join(format!("entry-{index}.txt")), "").unwrap(); }
        let checks = std::cell::Cell::new(0);
        let result = scan_paths(vec![path.clone()], true, || {
            checks.set(checks.get() + 1); checks.get() > 24
        });
        assert_eq!(result.unwrap_err(), "wallpaper_scan_cancelled");
        assert!(checks.get() > 24, "Cancellation occurs during traversal, not before it");
        let library = Arc::new(Library::default());
        let initial = library.begin_scan("initial".into()).unwrap();
        library.scan(initial, vec![path.clone()], true).unwrap();
        let known = library.known.lock().unwrap().clone(); assert_eq!(known.len(), 1);
        let guard = library.worker.lock().unwrap();
        let old = library.begin_scan("old".into()).unwrap();
        let worker_library = library.clone(); let old_path = path.clone();
        let (sender, receiver) = std::sync::mpsc::channel();
        let worker = std::thread::spawn(move || {
            sender.send(()).unwrap();
            worker_library.scan(old, vec![old_path], true)
        });
        receiver.recv().unwrap();
        let latest = library.begin_scan("latest".into()).unwrap();
        library.cancel_scan("old").unwrap(); // Late cleanup from an old UI cannot cancel its replacement.
        drop(guard);
        assert_eq!(worker.join().unwrap().unwrap_err(), "wallpaper_scan_cancelled");
        assert_eq!(*library.known.lock().unwrap(), known);
        let empty = path.join("empty"); fs::create_dir(&empty).unwrap();
        assert!(library.scan(latest, vec![empty], true).unwrap().images.is_empty());
        assert!(library.known.lock().unwrap().is_empty());
        let cancelled = library.begin_scan("cancelled".into()).unwrap();
        library.cancel_scan("cancelled").unwrap();
        assert_eq!(library.scan(cancelled, vec![path.clone()], true).unwrap_err(), "wallpaper_scan_cancelled");
        assert!(library.known.lock().unwrap().is_empty());
        fs::remove_dir_all(path).unwrap();
    }
    #[test]
    fn thumbnail_cache_changes_when_source_changes_and_is_bounded() {
        let path = fixture(); let original = path.join("one.png"); let cache = path.join("cache"); fs::create_dir(&cache).unwrap();
        image(&original, 32); let first = make_thumbnail(&original, &cache).unwrap();
        assert_eq!(make_thumbnail(&original, &cache).unwrap(), first);
        image(&original, 48); let second = make_thumbnail(&original, &cache).unwrap(); assert_ne!(first, second);
        let thumbnail = Pixbuf::from_file(&second).unwrap(); assert!(thumbnail.width() <= 320 && thumbnail.height() <= 200);
        for i in 0..520 { fs::write(cache.join(format!("unused-{i}")), "x").unwrap(); }
        trim_cache(&cache); assert_eq!(fs::read_dir(&cache).unwrap().count(), 512);
        fs::remove_dir_all(path).unwrap();
    }
}

thread_local! {
    // GSettings change delivery belongs to the creating main context. Retain the
    // objects instead of dropping delayed-write objects after each command.
    static GNOME_SETTINGS: std::cell::RefCell<std::collections::HashMap<&'static str, gio::Settings>> = std::cell::RefCell::new(std::collections::HashMap::new());
}
fn settings_for(name: &'static str) -> Result<gio::Settings, String> {
    use gio::prelude::*;
    GNOME_SETTINGS.with(|cache| {
        let mut cache = cache.borrow_mut();
        if let Some(settings) = cache.get(name) { return Ok(settings.clone()); }
        let schema = gio::SettingsSchemaSource::default().and_then(|source| source.lookup(name, true)).ok_or_else(|| format!("Settings schema unavailable: {name}"))?;
        let settings = gio::Settings::new_full(&schema, None::<&gio::SettingsBackend>, None);
        settings.connect_changed(None, |_, _| {});
        cache.insert(name, settings.clone());
        Ok(settings)
    })
}
fn gnome_settings() -> Result<gio::Settings, String> {
    use gio::prelude::*;
    let desktop = std::env::var("XDG_CURRENT_DESKTOP").unwrap_or_default().to_uppercase();
    if !desktop.split(':').any(|name| name == "GNOME") { return Err("wallpaper_adapter_unsupported: Wallpaper changes are supported on the verified GNOME adapter only".into()); }
    let settings = settings_for("org.gnome.desktop.background").map_err(|error| format!("wallpaper_schema_unavailable: {error}"))?;
    if !settings.settings_schema().is_some_and(|schema| schema.has_key("picture-uri")) { return Err("wallpaper_setting_unavailable: GNOME picture-uri setting is unavailable".into()); }
    Ok(settings)
}
pub fn availability() -> Result<(), String> {
    use gio::prelude::*;
    let settings = gnome_settings()?;
    let has_dark = settings.settings_schema().is_some_and(|schema| schema.has_key("picture-uri-dark"));
    if !settings.is_writable("picture-uri") || (has_dark && !settings.is_writable("picture-uri-dark")) {
        return Err("wallpaper_read_only: Wallpaper settings are read-only".into());
    }
    Ok(())
}
pub fn current_wallpaper() -> Result<String, String> {
    use gio::prelude::*;
    let settings = gnome_settings()?;
    let dark = settings_for("org.gnome.desktop.interface").ok().filter(|settings| settings.settings_schema().is_some_and(|schema| schema.has_key("color-scheme")))
        .is_some_and(|settings| settings.string("color-scheme") == "prefer-dark");
    let key = if dark && settings.settings_schema().is_some_and(|schema| schema.has_key("picture-uri-dark")) { "picture-uri-dark" } else { "picture-uri" };
    let uri = settings.string(key);
    if uri.is_empty() { return Ok(String::new()); }
    Ok(gio::File::for_uri(&uri).path().map(|p| p.to_string_lossy().into_owned()).unwrap_or_else(|| uri.to_string()))
}
fn prepare_wallpaper(path: &str) -> Result<String, String> {
    use gio::prelude::*;
    let file = if path.starts_with("file://") { gio::File::for_uri(path).path().ok_or("Not a local image URI")? } else { PathBuf::from(path) };
    if !file.is_absolute() { return Err("Select an absolute image path".into()); }
    let file = file.canonicalize().map_err(|e| e.to_string())?;
    image_info(&file)?;
    Pixbuf::from_file_at_scale(&file, 8, 8, true).map_err(|e| e.to_string())?;
    Ok(gio::File::for_path(&file).uri().to_string())
}
fn write_wallpaper_uri(uri: &str) -> Result<bool, String> {
    use gio::prelude::*;
    let settings = gnome_settings()?;
    let has_dark = settings.settings_schema().is_some_and(|schema| schema.has_key("picture-uri-dark"));
    if !settings.is_writable("picture-uri") || (has_dark && !settings.is_writable("picture-uri-dark")) { return Err("Wallpaper settings are read-only".into()); }
    settings.delay();
    if let Err(e) = settings.set_string("picture-uri", uri).and_then(|_| if has_dark { settings.set_string("picture-uri-dark", uri) } else { Ok(()) }) {
        settings.revert(); return Err(e.to_string());
    }
    settings.apply(); gio::Settings::sync();
    if settings.string("picture-uri") != uri || (has_dark && settings.string("picture-uri-dark") != uri) { return Err("Wallpaper settings did not retain the requested image".into()); }
    Ok(true)
}
fn on_main<T: Send + 'static>(app: &AppHandle, task: impl FnOnce() -> Result<T, String> + Send + 'static) -> Result<T, String> {
    let (send, receive) = std::sync::mpsc::sync_channel(1);
    app.run_on_main_thread(move || { let _ = send.send(task()); }).map_err(|e| e.to_string())?;
    receive.recv().map_err(|e| e.to_string())?
}
pub fn choose_image<'a>(images: &'a [Image], current: &str) -> Option<&'a Image> {
    use rand::seq::IteratorRandom;
    images.iter().filter(|image| image.path != current).choose(&mut rand::thread_rng()).or_else(|| images.first())
}
#[tauri::command]
pub async fn shuffle_wallpaper(app: AppHandle) -> Result<String, String> {
    let config = app.state::<crate::config::ConfigState>().0.lock().map_err(|e| e.to_string())?.snapshot.config.clone();
    let library = app.state::<WallpaperState>().0.clone();
    tauri::async_runtime::spawn_blocking(move || {
        let _worker = library.worker.lock().map_err(|e| e.to_string())?;
        let scan = scan_paths(configured_folders(&config), config["wallpaperRecursive"] == true, || false)?;
        let _apply = library.apply.lock().map_err(|e| e.to_string())?;
        let current = on_main(&app, current_wallpaper)?;
        let image = choose_image(&scan.images, &current).ok_or("No readable images in the configured wallpaper folders")?;
        let uri = prepare_wallpaper(&image.path)?;
        on_main(&app, move || write_wallpaper_uri(&uri))?;
        Ok(image.path.clone())
    }).await.map_err(|e| e.to_string())?
}

#[derive(Clone, Default, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ScheduleStatus {
    enabled: bool, running: bool, next_run_unix_ms: Option<u64>, last_run_unix_ms: Option<u64>,
    last_path: Option<String>, last_error: Option<String>,
}
#[derive(Default)]
struct Scheduler {
    started: AtomicBool, stopped: AtomicBool, epoch: AtomicU64,
    wake: (Mutex<bool>, std::sync::Condvar), status: Mutex<ScheduleStatus>,
}
#[derive(Default)]
struct ScheduleClock { key: Option<String>, interval_ms: Option<u64>, due: Option<u64> }
impl ScheduleClock {
    fn tick(&mut self, key: String, interval_ms: Option<u64>, now: u64) -> bool {
        let changed = self.key.as_ref() != Some(&key);
        self.key = Some(key); self.interval_ms = interval_ms;
        let Some(interval) = interval_ms else { self.due = None; return false; };
        // Reset after settings changes and backwards clock adjustments. Forward jumps
        // (including resume from sleep) cause one attempt, never a catch-up burst.
        if changed || self.due.is_none_or(|due| due > now.saturating_add(interval)) {
            self.due = Some(now.saturating_add(interval)); return false;
        }
        if self.due.is_some_and(|due| now >= due) {
            self.due = Some(now.saturating_add(interval)); return true;
        }
        false
    }
    fn finish(&mut self, now: u64) { self.due = self.interval_ms.map(|interval| now.saturating_add(interval)); }
}
fn now_ms() -> u64 { std::time::SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_millis().min(u128::from(u64::MAX)) as u64 }
fn schedule_key(config: &serde_json::Value) -> String {
    serde_json::json!([config["wallpaperScheduleEnabled"], config["wallpaperIntervalMinutes"], config["wallpaperFolders"], config["wallpaperRecursive"]]).to_string()
}
pub fn schedule_changed(app: &AppHandle) {
    let library = app.state::<WallpaperState>().0.clone();
    library.scheduler.epoch.fetch_add(1, Ordering::SeqCst);
    if let Ok(mut wake) = library.scheduler.wake.0.lock() { *wake = true; library.scheduler.wake.1.notify_one(); };
}
pub fn apply_manual(app: &AppHandle, library: &Library, path: &str) -> Result<bool, String> {
    let _apply = library.apply.lock().map_err(|e| e.to_string())?;
    let uri = prepare_wallpaper(path)?;
    on_main(app, move || write_wallpaper_uri(&uri))
}
#[tauri::command]
pub fn get_wallpaper_schedule_status(state: tauri::State<WallpaperState>) -> Result<ScheduleStatus, String> {
    let _trace = crate::diagnostics::command("get_wallpaper_schedule_status");
    state.0.scheduler.status.lock().map(|status| status.clone()).map_err(|e| e.to_string())
}
pub fn start_scheduler(app: &AppHandle) {
    let library = app.state::<WallpaperState>().0.clone();
    if library.scheduler.started.swap(true, Ordering::SeqCst) { return; }
    let app = app.clone();
    std::thread::spawn(move || {
        let mut clock = ScheduleClock::default();
        while !library.scheduler.stopped.load(Ordering::SeqCst) {
            // Release the configuration lock before scanning or waiting for IO workers.
            let state = app.state::<crate::config::ConfigState>();
            let snapshot = state.0.lock().map(|store| (store.initialized, store.snapshot.config.clone())).map_err(|e| e.to_string());
            if let Ok((initialized, config)) = snapshot {
                let epoch = library.scheduler.epoch.load(Ordering::SeqCst);
                let key = schedule_key(&config);
                let enabled = initialized && config["wallpaperScheduleEnabled"] == true;
                let interval = if enabled { Some(config["wallpaperIntervalMinutes"].as_u64().unwrap_or(15).clamp(1,1440) * 60_000) } else { None };
                let changed = clock.key.as_ref() != Some(&key);
                let due = clock.tick(key, interval, now_ms());
                if let Ok(mut status) = library.scheduler.status.lock() {
                    status.enabled = enabled; status.next_run_unix_ms = clock.due;
                    if changed { status.last_error = None; }
                    if due { status.running = true; }
                }
                if due {
                    let cancelled = || library.scheduler.stopped.load(Ordering::SeqCst) || library.scheduler.epoch.load(Ordering::SeqCst) != epoch;
                    let result = (|| -> Result<Option<String>, String> {
                        let _worker = library.worker.lock().map_err(|e| e.to_string())?;
                        let scan = scan_paths(configured_folders(&config), config["wallpaperRecursive"] == true, cancelled)?;
                        if cancelled() { return Ok(None); }
                        let _apply = library.apply.lock().map_err(|e| e.to_string())?;
                        let current = on_main(&app, current_wallpaper)?;
                        let image = choose_image(&scan.images, &current).ok_or("No readable images in the configured wallpaper folders")?;
                        let path = image.path.clone();
                        let uri = prepare_wallpaper(&path)?;
                        let app_for_apply = app.clone();
                        let library_for_apply = library.clone();
                        let key = schedule_key(&config);
                        // Only the small native settings transaction runs on GTK's
                        // main context. Decode and filesystem work stay off the UI.
                        on_main(&app, move || {
                            let state = app_for_apply.state::<crate::config::ConfigState>();
                            let store = state.0.lock().map_err(|e| e.to_string())?;
                            if library_for_apply.scheduler.stopped.load(Ordering::SeqCst) || library_for_apply.scheduler.epoch.load(Ordering::SeqCst) != epoch || !store.initialized || store.snapshot.config["wallpaperScheduleEnabled"] != true || schedule_key(&store.snapshot.config) != key { return Ok(None); }
                            write_wallpaper_uri(&uri)?;
                            Ok(Some(path))
                        })
                    })();
                    clock.finish(now_ms());
                    if let Ok(mut status) = library.scheduler.status.lock() {
                        status.running = false; status.next_run_unix_ms = clock.due;
                        if !cancelled() {
                            status.last_run_unix_ms = Some(now_ms());
                            match result {
                                Ok(Some(path)) => { status.last_path = Some(path); status.last_error = None; },
                                Err(error) => status.last_error = Some(error),
                                _ => {},
                            }
                        }
                    }
                }
            }
            let (lock, wake) = &library.scheduler.wake;
            if let Ok(mut changed) = lock.lock() {
                if !*changed && !library.scheduler.stopped.load(Ordering::SeqCst) {
                    if let Ok((mut changed, _)) = wake.wait_timeout(changed, std::time::Duration::from_secs(1)) { *changed = false; }
                } else { *changed = false; }
            }
        }
    });
}
pub fn stop_scheduler(app: &AppHandle) {
    let library = app.state::<WallpaperState>().0.clone();
    library.scheduler.stopped.store(true, Ordering::SeqCst);
    schedule_changed(app);
}
