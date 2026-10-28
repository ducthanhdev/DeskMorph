//! MPRIS controls target a unique bus owner, never a newly substituted player.
use gio::{glib::{self, prelude::*, VariantDict, FromVariant}, DBusCallFlags};
use serde::Serialize;
use tauri::{AppHandle, Emitter};
use std::{sync::{Arc, atomic::{AtomicBool, Ordering}, Mutex}, time::{Duration, Instant}};
const PATH: &str = "/org/mpris/MediaPlayer2";
const PLAYER: &str = "org.mpris.MediaPlayer2.Player";
#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Player {
    pub name: String, pub owner: String, pub identity: String, pub title: String, pub artists: Vec<String>,
    pub art_url: String, pub status: String, pub can_play: bool, pub can_pause: bool, pub can_next: bool, pub can_previous: bool,
}
fn bus() -> Result<gio::DBusConnection, String> {
    let connection = gio::bus_get_sync(gio::BusType::Session, gio::Cancellable::NONE).map_err(|e| format!("media_bus: {e}"))?;
    connection.set_exit_on_close(false);
    Ok(connection)
}
fn call(connection: &gio::DBusConnection, name: &str, path: &str, interface: &str, method: &str, args: Option<&glib::Variant>) -> Result<glib::Variant, String> {
    let reply = connection.call_sync(Some(name), path, interface, method, args, None, DBusCallFlags::NO_AUTO_START, 1500, gio::Cancellable::NONE).map_err(|e| format!("media_call: {e}"))?;
    let signature = match method { "GetAll" => "(a{sv})", "ListNames" => "(as)", "GetNameOwner" => "(s)", _ => "()" };
    if reply.type_().as_str() != signature { return Err("media_invalid_response".into()); }
    Ok(reply)
}
fn owner(connection: &gio::DBusConnection, name: &str) -> Result<String, String> {
    call(connection, "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "GetNameOwner", Some(&(name,).to_variant()))?.child_value(0).get::<String>().ok_or("media_owner_response".into())
}
fn properties(connection: &gio::DBusConnection, name: &str, interface: &str) -> Result<VariantDict, String> {
    let reply = call(connection, name, PATH, "org.freedesktop.DBus.Properties", "GetAll", Some(&(interface,).to_variant()))?;
    VariantDict::from_variant(&reply.child_value(0)).ok_or("media_properties_response".into())
}
fn boolean(dict: &VariantDict, key: &str) -> bool { dict.lookup::<bool>(key).ok().flatten().unwrap_or(false) }
fn string(dict: &VariantDict, key: &str) -> String { dict.lookup::<String>(key).ok().flatten().unwrap_or_default().chars().take(2048).collect() }
fn player(connection: &gio::DBusConnection, name: &str) -> Result<Player, String> {
    let owner = owner(connection, name)?;
    let props = properties(connection, &owner, PLAYER)?;
    let root = properties(connection, &owner, "org.mpris.MediaPlayer2")?;
    let metadata = props.lookup_value("Metadata", None).and_then(|value| VariantDict::from_variant(&value)).unwrap_or_default();
    let control = boolean(&props, "CanControl");
    Ok(Player { name: name.into(), owner, identity: string(&root, "Identity"), title: string(&metadata, "xesam:title"),
        artists: metadata.lookup::<Vec<String>>("xesam:artist").ok().flatten().unwrap_or_default().into_iter().take(16).map(|artist| artist.chars().take(256).collect()).collect(),
        art_url: string(&metadata, "mpris:artUrl"), status: string(&props, "PlaybackStatus"), can_play: control && boolean(&props, "CanPlay"), can_pause: control && boolean(&props, "CanPause"),
        can_next: control && boolean(&props, "CanGoNext"), can_previous: control && boolean(&props, "CanGoPrevious") })
}
fn discover() -> Result<Vec<Player>, String> {
    let connection = bus()?;
    let names = call(&connection, "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "ListNames", None)?.child_value(0).get::<Vec<String>>().ok_or("media_names_response")?;
    let mut names: Vec<_> = names.into_iter().filter(|name| name.starts_with("org.mpris.MediaPlayer2.")).collect(); names.sort(); names.truncate(16);
    // A player disappearing or rejecting properties must not hide the other players.
    let deadline = Instant::now() + Duration::from_secs(4);
    let mut players = Vec::new();
    for name in &names {
        if Instant::now() >= deadline { break; }
        if let Ok(value) = player(&connection, name) { players.push(value); }
    }
    players.sort_by(|a, b| (a.status != "Playing").cmp(&(b.status != "Playing")).then_with(|| a.name.cmp(&b.name)));
    Ok(players)
}
#[tauri::command]
pub async fn get_media_players() -> Result<Vec<Player>, String> { tauri::async_runtime::spawn_blocking(discover).await.map_err(|e| e.to_string())? }
#[tauri::command]
pub async fn control_media(name: String, expected_owner: String, action: String) -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(move || {
        if !name.starts_with("org.mpris.MediaPlayer2.") { return Err("media_invalid_player".into()); }
        let connection = bus()?;
        let selected = player(&connection, &name)?;
        if selected.owner != expected_owner { return Err("media_player_replaced".into()); }
        let allowed = match action.as_str() { "Play" => selected.can_play, "Pause" => selected.can_pause, "Next" => selected.can_next, "Previous" => selected.can_previous, _ => false };
        if !allowed { return Err("media_action_unsupported".into()); }
        call(&connection, &expected_owner, PATH, PLAYER, &action, None)?; Ok(())
    }).await.map_err(|e| e.to_string())?
}
#[derive(Default)]
pub struct MediaState(Arc<AtomicBool>, Arc<Mutex<std::collections::VecDeque<(String, String)>>>);

fn artwork(url: &str, cache: &Mutex<std::collections::VecDeque<(String, String)>>) -> Result<Option<String>, String> {
    use std::hash::{Hash, Hasher};
    if url.is_empty() { return Ok(None); }
    if !url.starts_with("file:///") { return Err("media_artwork_local_only".into()); }
    use gio::prelude::FileExt;
    let path = gio::File::for_uri(url).path().ok_or("media_artwork_path")?;
    let metadata = std::fs::metadata(&path).map_err(|_| "media_artwork_missing")?;
    if !metadata.is_file() || metadata.len() > 8 * 1024 * 1024 { return Err("media_artwork_size".into()); }
    let mut hash = std::collections::hash_map::DefaultHasher::new();
    path.hash(&mut hash); metadata.len().hash(&mut hash); metadata.modified().ok().hash(&mut hash);
    let key = format!("{:x}", hash.finish());
    let mut cache = cache.lock().map_err(|_| "media_artwork_lock")?;
    if let Some((_, image)) = cache.iter().find(|(cached, _)| cached == &key) { return Ok(Some(image.clone())); }
    let (_, width, height) = gtk::gdk_pixbuf::Pixbuf::file_info(&path).ok_or("media_artwork_format")?;
    if width <= 0 || height <= 0 || width as u64 * height as u64 > 16_000_000 { return Err("media_artwork_dimensions".into()); }
    let image = gtk::gdk_pixbuf::Pixbuf::from_file_at_scale(&path, 160, 160, true).map_err(|_| "media_artwork_decode")?;
    let image = image.apply_embedded_orientation().unwrap_or(image);
    let bytes = image.save_to_bufferv("png", &[]).map_err(|_| "media_artwork_encode")?;
    let data = format!("data:image/png;base64,{}", glib::base64_encode(&bytes));
    if data.len() > 256 * 1024 { return Err("media_artwork_size".into()); }
    if cache.len() >= 16 { cache.pop_front(); }
    cache.push_back((key, data.clone()));
    Ok(Some(data))
}
#[tauri::command]
pub async fn get_media_artwork(app: AppHandle, name: String, expected_owner: String) -> Result<Option<String>, String> {
    use tauri::Manager;
    let cache = app.state::<MediaState>().1.clone();
    tauri::async_runtime::spawn_blocking(move || {
        if !name.starts_with("org.mpris.MediaPlayer2.") { return Err("media_invalid_player".into()); }
        let selected = player(&bus()?, &name)?;
        if selected.owner != expected_owner { return Err("media_player_replaced".into()); }
        artwork(&selected.art_url, &cache)
    }).await.map_err(|e| e.to_string())?
}
pub fn start(app: &AppHandle) {
    use tauri::Manager;
    let stop = app.state::<MediaState>().0.clone(); let app = app.clone();
    std::thread::spawn(move || {
        let context = glib::MainContext::new();
        let _ = context.with_thread_default(|| {
            while !stop.load(Ordering::Relaxed) {
                if !crate::popup::is_audio_active(&app) { std::thread::sleep(Duration::from_millis(100)); continue; }
                if let Ok(connection) = bus() {
                    let dirty = Arc::new(AtomicBool::new(true)); let changed = dirty.clone();
                    let props = connection.signal_subscribe(None, Some("org.freedesktop.DBus.Properties"), Some("PropertiesChanged"), Some(PATH), None, gio::DBusSignalFlags::NONE, move |_,_,_,_,_,_| { changed.store(true, Ordering::Relaxed); });
                    let changed = dirty.clone();
                    let names = connection.signal_subscribe(Some("org.freedesktop.DBus"), Some("org.freedesktop.DBus"), Some("NameOwnerChanged"), Some("/org/freedesktop/DBus"), None, gio::DBusSignalFlags::NONE, move |_,_,_,_,_,args| {
                        if args.child_value(0).str().is_some_and(|name| name.starts_with("org.mpris.MediaPlayer2.")) { changed.store(true, Ordering::Relaxed); }
                    });
                    let mut refreshed = Instant::now() - Duration::from_secs(1);
                    while !stop.load(Ordering::Relaxed) && crate::popup::is_audio_active(&app) && !connection.is_closed() {
                        for _ in 0..32 { if !context.pending() { break; } context.iteration(false); }
                        if dirty.load(Ordering::Relaxed) && refreshed.elapsed() >= Duration::from_millis(200) {
                            dirty.store(false, Ordering::Relaxed); let _ = app.emit("deskmorph:media", &discover()); refreshed = Instant::now();
                        }
                        std::thread::sleep(Duration::from_millis(100));
                    }
                    connection.signal_unsubscribe(props); connection.signal_unsubscribe(names);
                } else { let _ = app.emit("deskmorph:media", &Err::<Vec<Player>, _>("media_bus_unavailable")); }
                for _ in 0..20 { if stop.load(Ordering::Relaxed) || !crate::popup::is_audio_active(&app) { break; } std::thread::sleep(Duration::from_millis(100)); }
            }
        });
    });
}
pub fn stop(app: &AppHandle) { use tauri::Manager; app.state::<MediaState>().0.store(true, Ordering::Relaxed); }

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn artwork_is_local_bounded_cached_and_invalidated() {
        use gio::prelude::FileExt;
        let cache = Mutex::new(std::collections::VecDeque::new());
        assert!(artwork("https://example.invalid/cover.png", &cache).is_err());
        assert!(artwork("", &cache).unwrap().is_none());
        let root = std::env::temp_dir().join(format!("deskmorph-media-art-{}-{}", std::process::id(), std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos()));
        std::fs::create_dir_all(&root).unwrap();
        let image = gtk::gdk_pixbuf::Pixbuf::new(gtk::gdk_pixbuf::Colorspace::Rgb, false, 8, 32, 16).unwrap();
        image.fill(0xff00ffff);
        for i in 0..17 { let path = root.join(format!("{i}.png")); image.savev(&path, "png", &[]).unwrap(); assert!(artwork(gio::File::for_path(&path).uri().as_str(), &cache).unwrap().unwrap().starts_with("data:image/png;base64,")); }
        assert_eq!(cache.lock().unwrap().len(), 16);
        let path = root.join("16.png"); let uri = gio::File::for_path(&path).uri();
        let original = artwork(&uri, &cache).unwrap();
        image.fill(0x00ffffff); image.savev(&path, "png", &[]).unwrap();
        assert_ne!(original, artwork(&uri, &cache).unwrap());
        std::fs::write(&path, "broken").unwrap(); assert!(artwork(&uri, &cache).is_err());
        std::fs::remove_dir_all(root).unwrap();
    }
}
