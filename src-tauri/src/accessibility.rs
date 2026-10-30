//! GTK/ATK announcements for WebKitGTK versions without live-region events.
//! Keep the visible DOM feedback and its description; never move keyboard focus.
use tauri::{Manager, WebviewWindow};

fn valid_message(message: &str) -> bool {
    !message.trim().is_empty() && message.chars().count() <= 512
        && !message.chars().any(char::is_control)
}

fn eligible(label: &str, requested: u64, current: Option<u64>, visible: bool, focused: bool) -> bool {
    label == "dock-context-menu" && current == Some(requested) && visible && focused
}

#[tauri::command]
pub async fn announce_accessibility(window: WebviewWindow, message: String, generation: u64) -> Result<bool, String> {
    if !valid_message(&message) { return Ok(false); }
    let check = window.clone();
    let (sender, receiver) = std::sync::mpsc::channel();
    window.run_on_main_thread(move || {
        use gtk::prelude::*;
        let sent = if eligible(check.label(), generation,
            crate::popup::active_generation(check.app_handle(), check.label()),
            check.is_visible().unwrap_or(false), check.is_focused().unwrap_or(false)) {
            check.gtk_window().ok().filter(|native| native.is_active()).and_then(|native| native.accessible()).map(|accessible| {
                // Runtime lookup also supports older ATK installations without
                // raising the packaged application's minimum ATK version.
                if gtk::glib::subclass::SignalId::lookup("notification", accessible.type_()).is_some() {
                    // ATK_LIVE_ASSERTIVE = 2; the signal's argument is a gint.
                    accessible.emit_by_name::<()>("notification", &[&message, &2i32]);
                    true
                } else if gtk::glib::subclass::SignalId::lookup("announcement", accessible.type_()).is_some() {
                    accessible.emit_by_name::<()>("announcement", &[&message]);
                    true
                } else { false }
            }).unwrap_or(false)
        } else { false };
        let _ = sender.send(sent);
    }).map_err(|error| error.to_string())?;
    tauri::async_runtime::spawn_blocking(move || receiver.recv_timeout(std::time::Duration::from_secs(2)))
        .await.map_err(|error| error.to_string())?.map_err(|error| error.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn announcements_require_current_visible_focused_popup() {
        assert!(eligible("dock-context-menu", 4, Some(4), true, true));
        for (label, current, visible, focused) in [
            ("main", Some(4), true, true), ("dock-context-menu", Some(3), true, true),
            ("dock-context-menu", None, true, true), ("dock-context-menu", Some(4), false, true),
            ("dock-context-menu", Some(4), true, false),
        ] { assert!(!eligible(label, 4, current, visible, focused)); }
    }
    #[test]
    fn announcement_text_is_bounded_and_not_raw_control_data() {
        assert!(valid_message("Không mở được ứng dụng"));
        assert!(valid_message(&"ộ".repeat(512)));
        for text in ["", "  ", "message\0diagnostic", "message\nnext line", &"ộ".repeat(513)] {
            assert!(!valid_message(text));
        }
    }
}
