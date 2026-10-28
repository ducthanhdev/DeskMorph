//! Opt-in X11 passive key grabs on a private XCB connection. Never changes the
//! process-wide Xlib error handler used by GTK, and never grabs AnyModifier.
use serde::Serialize;
use std::{ffi::c_void, sync::{mpsc, Arc, Mutex}, thread, time::Duration};
use tauri::{AppHandle, Manager};

#[derive(Clone, Copy, Debug, PartialEq)]
struct Chord { modifiers: u16, keysym: u32 }
fn parse(value: &str) -> Result<Chord, String> {
    let parts: Vec<_> = value.split('+').collect();
    if parts.len() < 2 || value.len() > 64 { return Err("shortcut_invalid".into()); }
    let mut modifiers = 0;
    for part in &parts[..parts.len() - 1] {
        let bit = match *part { "Ctrl" => 4, "Alt" => 8, "Shift" => 1, "Super" => 64, _ => return Err("shortcut_invalid".into()) };
        if modifiers & bit != 0 { return Err("shortcut_invalid".into()); }
        modifiers |= bit;
    }
    // Bare keys and Shift-only would intercept normal typing.
    if modifiers & (4 | 8 | 64) == 0 { return Err("shortcut_invalid".into()); }
    let key = parts[parts.len() - 1];
    let keysym = if key == "Space" { 0x20 }
        else if key.len() == 1 && key.as_bytes()[0].is_ascii_alphanumeric() { key.as_bytes()[0].to_ascii_lowercase() as u32 }
        else if let Some(number) = key.strip_prefix('F').and_then(|v| v.parse::<u32>().ok()).filter(|n| (1..=12).contains(n)) { 0xffbd + number }
        else { return Err("shortcut_invalid".into()); };
    // Xorg may process virtual-terminal switching before passive grabs. These
    // combinations cannot be safely checked for desktop ownership with XCB.
    if modifiers & 12 == 12 && (0xffbe..=0xffc9).contains(&keysym) { return Err("shortcut_reserved".into()); }
    Ok(Chord { modifiers, keysym })
}
pub fn valid(value: &str) -> bool { parse(value).is_ok() }

#[derive(Clone, Default, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Status {
    requested: Option<String>, registered: bool, pending: bool, error: Option<String>,
    #[serde(skip)] generation: u64,
}
enum Command { Configure(u64, Option<String>), Stop }
#[derive(Default)]
pub struct ShortcutState {
    status: Arc<Mutex<Status>>,
    sender: Mutex<Option<mpsc::Sender<Command>>>,
    worker: Mutex<Option<thread::JoinHandle<()>>>,
}
fn finish(status: &Mutex<Status>, generation: u64, registered: bool, error: Option<String>) -> bool {
    if let Ok(mut status) = status.lock() {
        if status.generation == generation { status.registered = registered; status.pending = false; status.error = error; return true; }
    }
    false
}
pub fn start(app: &AppHandle) {
    let state = app.state::<ShortcutState>();
    let (sender, receiver) = mpsc::channel();
    *state.sender.lock().unwrap() = Some(sender);
    let status = state.status.clone();
    let handle = app.clone();
    *state.worker.lock().unwrap() = Some(thread::spawn(move || {
        let mut binding: Option<Binding> = None;
        let mut generation = 0;
        let mut held = false;
        loop {
            let command = if binding.is_some() { receiver.recv_timeout(Duration::from_millis(40)) }
                else { receiver.recv().map_err(|_| mpsc::RecvTimeoutError::Disconnected) };
            match command {
                Ok(Command::Stop) | Err(mpsc::RecvTimeoutError::Disconnected) => break,
                Ok(Command::Configure(next, requested)) => {
                    binding = None; held = false; generation = next;
                    if let Some(requested) = requested {
                        let result = if std::env::var("XDG_SESSION_TYPE").as_deref() == Ok("x11") {
                            parse(&requested).and_then(Binding::open)
                        } else { Err("shortcut_unsupported".into()) };
                        match result {
                            Ok(value) => { if finish(&status, generation, true, None) { binding = Some(value); } }
                            Err(error) => { finish(&status, generation, false, Some(error)); }
                        }
                    } else { finish(&status, generation, false, None); }
                }
                Err(mpsc::RecvTimeoutError::Timeout) => (),
            }
            let Some(current) = binding.as_ref() else { continue; };
            if unsafe { xcb_connection_has_error(current.connection) } != 0 {
                finish(&status, generation, false, Some("shortcut_connection".into())); binding = None; continue;
            }
            let mut remap = false;
            while let Some(event) = current.event() {
                match event[0] & 0x7f {
                    2 if event[0] & 0x80 == 0 && event[1] == current.keycode && !held => {
                        let modifiers = u16::from_ne_bytes([event[28], event[29]]) & 0xff & !current.locks;
                        if modifiers != current.modifiers { continue; }
                        held = true;
                        let active = status.lock().is_ok_and(|s| s.generation == generation && s.registered);
                        if active {
                            let timestamp = u32::from_ne_bytes(event[4..8].try_into().unwrap());
                            let app = handle.clone();
                            let status = status.clone();
                            let _ = handle.run_on_main_thread(move || {
                                // A save/disable may have happened while GTK was busy.
                                if !status.lock().is_ok_and(|s| s.generation == generation && s.registered) { return; }
                                let result = super::show_app_launcher(app.clone()).and_then(|_| super::popup::focus_at(&app, "dock-context-menu", timestamp));
                                if let Err(error) = result {
                                    if let Ok(mut s) = status.lock() { if s.generation == generation { s.error = Some(format!("shortcut_open: {error}")); } }
                                }
                            });
                        }
                    }
                    34 => remap = true, // Keyboard/modifier mapping changed.
                    _ => (),
                }
            }
            // Physical state avoids duplicate launches from synthetic X11
            // autorepeat release/press pairs while the key is held down.
            if held && !current.key_down() { held = false; }
            if remap {
                let chord = current.chord;
                binding = None; held = false;
                match Binding::open(chord) {
                    Ok(value) => { if finish(&status, generation, true, None) { binding = Some(value); } }
                    Err(error) => { finish(&status, generation, false, Some(error)); }
                }
            }
        }
        // Closing our connection releases only our passive grabs.
    }));
}
pub fn configure(app: &AppHandle, value: Option<&str>) {
    let state = app.state::<ShortcutState>();
    let generation = {
        let mut s = state.status.lock().unwrap();
        s.generation = s.generation.wrapping_add(1); s.requested = value.map(str::to_owned);
        s.pending = value.is_some(); s.registered = false; s.error = None; s.generation
    };
    if !state.sender.lock().unwrap().as_ref().is_some_and(|sender| sender.send(Command::Configure(generation, value.map(str::to_owned))).is_ok()) {
        finish(&state.status, generation, false, Some("shortcut_worker".into()));
    }
}
pub fn stop(app: &AppHandle) {
    let state = app.state::<ShortcutState>();
    if let Some(sender) = state.sender.lock().unwrap().take() { let _ = sender.send(Command::Stop); }
    let worker = state.worker.lock().unwrap().take();
    if let Some(worker) = worker { let _ = worker.join(); }
}
#[tauri::command]
pub fn get_launcher_shortcut_status(state: tauri::State<ShortcutState>) -> Result<Status, String> {
    state.status.lock().map(|s| s.clone()).map_err(|e| e.to_string())
}
#[tauri::command]
pub fn retry_launcher_shortcut(app: AppHandle) -> Result<(), String> {
    let config = app.state::<super::config::ConfigState>().0.lock().map_err(|e| e.to_string())?.snapshot.config.clone();
    configure(&app, if config["enabled"] == true { config["launcherShortcut"].as_str() } else { None });
    Ok(())
}

#[repr(C)]
#[derive(Clone, Copy)]
struct Cookie { sequence: u32 }
#[repr(C)]
struct Iterator { data: *const u32, remaining: i32, index: i32 }
#[repr(C)]
struct Setup { header: [u8; 34], min_keycode: u8, max_keycode: u8, pad: [u8; 4] }
#[repr(C)]
struct MappingReply { response: u8, count: u8, sequence: u16, length: u32, pad: [u8; 24] }
#[link(name = "xcb")]
extern "C" {
    fn xcb_connect(display: *const i8, screen: *mut i32) -> *mut c_void;
    fn xcb_disconnect(connection: *mut c_void);
    fn xcb_connection_has_error(connection: *mut c_void) -> i32;
    fn xcb_get_setup(connection: *mut c_void) -> *const Setup;
    fn xcb_setup_roots_iterator(setup: *const Setup) -> Iterator;
    fn xcb_screen_next(iterator: *mut Iterator);
    fn xcb_get_keyboard_mapping(connection: *mut c_void, first: u8, count: u8) -> Cookie;
    fn xcb_get_keyboard_mapping_reply(connection: *mut c_void, cookie: Cookie, error: *mut *mut c_void) -> *mut MappingReply;
    fn xcb_get_keyboard_mapping_keysyms(reply: *const MappingReply) -> *const u32;
    fn xcb_get_modifier_mapping(connection: *mut c_void) -> Cookie;
    fn xcb_get_modifier_mapping_reply(connection: *mut c_void, cookie: Cookie, error: *mut *mut c_void) -> *mut MappingReply;
    fn xcb_get_modifier_mapping_keycodes(reply: *const MappingReply) -> *const u8;
    fn xcb_grab_key_checked(connection: *mut c_void, owner_events: u8, root: u32, modifiers: u16, key: u8, pointer_mode: u8, keyboard_mode: u8) -> Cookie;
    fn xcb_request_check(connection: *mut c_void, cookie: Cookie) -> *mut u8;
    fn xcb_poll_for_event(connection: *mut c_void) -> *mut u8;
    fn xcb_query_keymap(connection: *mut c_void) -> Cookie;
    fn xcb_query_keymap_reply(connection: *mut c_void, cookie: Cookie, error: *mut *mut c_void) -> *mut u8;
    fn free(pointer: *mut c_void);
}
struct Binding { connection: *mut c_void, keycode: u8, locks: u16, modifiers: u16, chord: Chord }
impl Drop for Binding { fn drop(&mut self) { unsafe { xcb_disconnect(self.connection); } } }
impl Binding {
    fn open(chord: Chord) -> Result<Self, String> { unsafe {
        let mut screen = 0;
        let connection = xcb_connect(std::ptr::null(), &mut screen);
        if connection.is_null() { return Err("shortcut_connection".into()); }
        let mut binding = Self { connection, keycode: 0, locks: 0, modifiers: 0, chord };
        if xcb_connection_has_error(connection) != 0 { return Err("shortcut_connection".into()); }
        let setup = xcb_get_setup(connection);
        if setup.is_null() { return Err("shortcut_connection".into()); }
        let mut roots = xcb_setup_roots_iterator(setup);
        for _ in 0..screen { xcb_screen_next(&mut roots); }
        if roots.remaining <= 0 || roots.data.is_null() { return Err("shortcut_connection".into()); }
        let root = *roots.data;
        let first = (*setup).min_keycode;
        let count = (*setup).max_keycode.checked_sub(first).and_then(|n| n.checked_add(1)).ok_or("shortcut_keymap")?;
        let reply = xcb_get_keyboard_mapping_reply(connection, xcb_get_keyboard_mapping(connection, first, count), std::ptr::null_mut());
        if reply.is_null() { return Err("shortcut_keymap".into()); }
        let width = (*reply).count as usize;
        if width == 0 || width * count as usize > (*reply).length as usize * 4 { free(reply.cast()); return Err("shortcut_keymap".into()); }
        let mapping = std::slice::from_raw_parts(xcb_get_keyboard_mapping_keysyms(reply), width * count as usize).to_vec();
        free(reply.cast());
        if width == 0 { return Err("shortcut_keymap".into()); }
        binding.keycode = mapping.chunks(width).position(|syms| syms.first() == Some(&chord.keysym))
            .map(|index| first + index as u8).ok_or("shortcut_key_missing")?;
        let reply = xcb_get_modifier_mapping_reply(connection, xcb_get_modifier_mapping(connection), std::ptr::null_mut());
        if reply.is_null() { return Err("shortcut_keymap".into()); }
        let width_mod = (*reply).count as usize;
        if width_mod * 8 > (*reply).length as usize * 4 { free(reply.cast()); return Err("shortcut_keymap".into()); }
        let codes = std::slice::from_raw_parts(xcb_get_modifier_mapping_keycodes(reply), width_mod * 8);
        let mut modifier_masks = [0u16; 4];
        for modifier in 0..8 {
            for code in &codes[modifier * width_mod..(modifier + 1) * width_mod] {
                if *code >= first && (*code - first) < count {
                    let start = (*code - first) as usize * width;
                    let symbols = &mapping[start..start + width];
                    if symbols.iter().any(|symbol| matches!(symbol, 0xffe5 | 0xff7f | 0xff14)) { binding.locks |= 1 << modifier; }
                    for (index, pair) in [(0xffe1, 0xffe2), (0xffe3, 0xffe4), (0xffe9, 0xffea), (0xffeb, 0xffec)].iter().enumerate() {
                        if symbols.iter().any(|symbol| *symbol == pair.0 || *symbol == pair.1) { modifier_masks[index] |= 1 << modifier; }
                    }
                }
            }
        }
        free(reply.cast());
        for (index, logical) in [1, 4, 8, 64].iter().enumerate() {
            if chord.modifiers & logical != 0 {
                if modifier_masks[index].count_ones() != 1 { return Err("shortcut_keymap".into()); }
                binding.modifiers |= modifier_masks[index];
            }
        }
        // Do not ignore an explicit modifier even on unusual keymaps.
        binding.locks &= !binding.modifiers;
        for lock_mask in 0u16..256 {
            if lock_mask & !binding.locks != 0 { continue; }
            let error = xcb_request_check(connection, xcb_grab_key_checked(connection, 0, root, binding.modifiers | lock_mask, binding.keycode, 1, 1));
            if !error.is_null() {
                let code = *error.add(1); free(error.cast());
                return Err(if code == 10 { "shortcut_conflict" } else { "shortcut_registration" }.into());
            }
        }
        Ok(binding)
    } }
    fn event(&self) -> Option<[u8; 32]> { unsafe {
        let pointer = xcb_poll_for_event(self.connection);
        if pointer.is_null() { return None; }
        let mut bytes = [0; 32]; bytes.copy_from_slice(std::slice::from_raw_parts(pointer, 32)); free(pointer.cast()); Some(bytes)
    } }
    fn key_down(&self) -> bool { unsafe {
        let reply = xcb_query_keymap_reply(self.connection, xcb_query_keymap(self.connection), std::ptr::null_mut());
        if reply.is_null() { return false; }
        let down = *reply.add(8 + self.keycode as usize / 8) & (1 << (self.keycode % 8)) != 0;
        free(reply.cast()); down
    } }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn shortcut_parser_rejects_typing_and_ambiguous_or_duplicate_modifiers() {
        for value in ["A", "Shift+A", "Ctrl+Ctrl+L", "Alt++L", "Ctrl+F13", "Control+L", "Super+", "Ctrl+Escape", "Ctrl+F1+L", "Ctrl+Alt+F1", "Ctrl+Alt+Super+F12"] { assert!(!valid(value), "{value}"); }
        assert_eq!(parse("Ctrl+Shift+F12").unwrap(), Chord { modifiers: 5, keysym: 0xffc9 });
        assert_eq!(parse("Super+Shift+Space").unwrap(), Chord { modifiers: 65, keysym: 0x20 });
        assert_eq!(parse("Alt+X").unwrap(), parse("Alt+x").unwrap());
    }
    #[test]
    fn stale_registration_cannot_overwrite_a_newer_disable() {
        let status = Mutex::new(Status { generation: 2, ..Default::default() });
        assert!(!finish(&status, 1, true, None));
        assert!(!status.lock().unwrap().registered);
    }
    #[test]
    #[ignore = "requires a real X11 session; briefly registers an uncommon chord without sending input"]
    fn native_checked_grab_conflict_and_release() {
        let chord = parse("Ctrl+Alt+Super+K").unwrap();
        let first = Binding::open(chord).expect("reference test chord must be available; do not override an existing grab");
        assert!(matches!(Binding::open(chord), Err(error) if error == "shortcut_conflict"));
        drop(first);
        drop(Binding::open(chord).expect("disconnect must release every lock-mask variant"));
    }
}
