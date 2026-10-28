use super::{Capabilities, OpenWindow, WindowError, WindowId, WindowManager};
use std::os::raw::{c_char, c_int, c_long, c_uint, c_ulong, c_void};
use std::process::Command;


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
    pub(crate) fn XOpenDisplay(display_name: *const c_char) -> *mut c_void;
    pub(crate) fn XDefaultRootWindow(display: *mut c_void) -> c_ulong;
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
    pub(crate) fn XQueryPointer(
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
    pub(crate) fn XFlush(display: *mut c_void) -> c_int;
    pub(crate) fn XCloseDisplay(display: *mut c_void) -> c_int;
}

fn advertised(properties: &str, atom: &str) -> bool {
    properties
        .lines()
        .find(|line| line.starts_with("_NET_SUPPORTED(ATOM)"))
        .and_then(|line| line.split_once('='))
        .is_some_and(|(_, values)| values.split(',').any(|value| value.trim() == atom))
}

fn parse_capabilities(properties: &str) -> Capabilities {
    Capabilities {
        enumerate: client_ids(properties).is_ok(),
        activate: advertised(properties, "_NET_ACTIVE_WINDOW"),
        close: advertised(properties, "_NET_CLOSE_WINDOW"),
    }
}

/// Query the current WM, rather than treating DISPLAY/tool existence as proof.
fn capabilities() -> Result<Capabilities, String> {
    xprop(&["-root", "_NET_CLIENT_LIST", "_NET_SUPPORTED"])
        .map(|properties| parse_capabilities(&properties))
}

fn require_action(atom: &str) -> Result<(), String> {
    if advertised(&xprop(&["-root", "_NET_SUPPORTED"])?, atom) {
        Ok(())
    } else {
        Err(format!(
            "window_action_unsupported: Window manager không công bố {atom}"
        ))
    }
}

fn parse_xid(xid: &str) -> Result<u64, String> {
    let clean = xid.trim();
    if let Some(stripped) = clean
        .strip_prefix("0x")
        .or_else(|| clean.strip_prefix("0X"))
    {
        u64::from_str_radix(stripped, 16).map_err(|e| format!("window_target_invalid: Invalid hex XID '{xid}': {e}"))
    } else if let Ok(val) = clean.parse::<u64>() {
        Ok(val)
    } else {
        u64::from_str_radix(clean, 16).map_err(|e| format!("window_target_invalid: Invalid XID '{xid}': {e}"))
    }
}

fn listed_xid(xid: &str, clients: &str) -> Result<u64, String> {
    let id = parse_xid(xid)?;
    if id == 0 || id > u32::MAX as u64 {
        return Err("window_target_invalid".into());
    }
    let listed = client_ids(clients)?.contains(&id);
    if !listed {
        return Err("window_target_missing: Cửa sổ không còn trong danh sách quản lý".into());
    }
    Ok(id)
}
fn action_target(xid: &str) -> Result<u64, String> {
    let id = listed_xid(xid, &xprop(&["-root", "_NET_CLIENT_LIST"])?)?;
    let hex = format!("0x{id:x}");
    let info = xprop(&[
        "-id",
        &hex,
        "WM_CLASS",
        "_NET_WM_WINDOW_TYPE",
        "_NET_WM_PID",
    ])?;
    if parse_window(&hex, &info, None, std::process::id()).is_none() {
        return Err(
            "window_target_internal: Không thao tác cửa sổ nội bộ hay panel desktop".into(),
        );
    }
    Ok(id)
}

fn activate_window(window_id: String) -> Result<bool, String> {
    require_action("_NET_ACTIVE_WINDOW")?;
    let wid = action_target(&window_id)?;

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
        let sent = XSendEvent(display, root, 0, mask, &mut event);
        XFlush(display);
        XCloseDisplay(display);
        if sent == 0 {
            return Err("window_request_failed".into());
        }
    }

    Ok(true)
}

fn close_window(xid: String) -> Result<bool, String> {
    require_action("_NET_CLOSE_WINDOW")?;
    let wid = action_target(&xid)?;

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
        let sent = XSendEvent(display, root, 0, mask, &mut event);
        XFlush(display);
        XCloseDisplay(display);
        if sent == 0 {
            return Err("window_request_failed".into());
        }
    }

    Ok(true)
}

fn force_kill_window(xid: String) -> Result<bool, String> {
    let wid = action_target(&xid)?;
    // _NET_WM_PID is supplied by the client and is not an authority to SIGKILL a
    // process. Let the X server resolve resource ownership, in a child process
    // so a stale XID/BadWindow cannot invoke Xlib's fatal handler in DeskMorph.
    let output = Command::new("xkill")
        .args(["-id", &format!("0x{wid:x}")])
        .stdin(std::process::Stdio::null())
        .output()
        .map_err(|e| format!("force_quit_unavailable: {e}"))?;
    if !output.status.success() {
        return Err(format!(
            "force_quit_failed: {}",
            String::from_utf8_lossy(&output.stderr).trim()
        ));
    }
    Ok(true)
}

fn xprop(args: &[&str]) -> Result<String, String> {
    let output = Command::new("xprop")
        .args(args)
        .output()
        .map_err(|e| format!("xprop_unavailable: {e}"))?;
    if !output.status.success() {
        return Err(format!(
            "xprop_failed: {}",
            String::from_utf8_lossy(&output.stderr).trim()
        ));
    }
    Ok(String::from_utf8_lossy(&output.stdout).into_owned())
}
fn quoted_values(line: &str) -> Vec<String> {
    let mut result = Vec::new();
    let mut chars = line.chars();
    while let Some(c) = chars.next() {
        if c != '"' {
            continue;
        }
        let mut value = String::new();
        while let Some(c) = chars.next() {
            match c {
                '"' => break,
                '\\' => match chars.next() {
                    Some('n') => value.push('\n'),
                    Some('t') => value.push('\t'),
                    Some(c) => value.push(c),
                    None => break,
                },
                c => value.push(c),
            }
        }
        result.push(value);
    }
    result
}
fn property<'a>(info: &'a str, key: &str) -> Option<&'a str> {
    info.lines().find(|line| {
        line.strip_prefix(key)
            .is_some_and(|rest| rest.starts_with('('))
    })
}
fn client_ids(properties: &str) -> Result<Vec<u64>, String> {
    let line = properties.lines().find(|line| line.starts_with("_NET_CLIENT_LIST(WINDOW):"))
        .ok_or("window_manager_unsupported: X11 window manager không cung cấp _NET_CLIENT_LIST kiểu WINDOW")?;
    let (_, values) = line
        .split_once('#')
        .ok_or("window_list_invalid: _NET_CLIENT_LIST không đúng định dạng")?;
    if values.trim().is_empty() {
        return Ok(Vec::new());
    }
    values
        .split(',')
        .map(|value| {
            let id = parse_xid(value)?;
            if id == 0 || id > u32::MAX as u64 {
                return Err("window_list_invalid: XID ngoài phạm vi".into());
            }
            Ok(id)
        })
        .collect()
}
fn parse_window(wid: &str, info: &str, active: Option<u64>, own_pid: u32) -> Option<OpenWindow> {
    let excluded_type = property(info, "_NET_WM_WINDOW_TYPE")
        .and_then(|line| line.split_once('='))
        .is_some_and(|(_, values)| values.split(',').any(|value| matches!(value.trim(), "_NET_WM_WINDOW_TYPE_DOCK" | "_NET_WM_WINDOW_TYPE_DESKTOP")));
    if excluded_type {
        return None;
    }
    if property(info, "_NET_WM_PID")
        .and_then(|s| s.split_once('='))
        .and_then(|(_, v)| v.trim().parse::<u32>().ok())
        == Some(own_pid)
    {
        return None;
    }
    let class_name = property(info, "WM_CLASS")
        .map(quoted_values)
        .and_then(|values| values.last().cloned())
        .filter(|c| !c.is_empty())
        .unwrap_or_else(|| "App".into());
    let title = property(info, "_NET_WM_NAME")
        .or_else(|| property(info, "WM_NAME"))
        .map(quoted_values)
        .and_then(|values| values.into_iter().next())
        .unwrap_or_else(|| class_name.clone());
    let id = parse_xid(wid).ok()?;
    Some(OpenWindow {
        id: WindowId::from(format!("0x{id:x}")),
        class_name,
        title,
        is_active: active == Some(id),
    })
}
fn list() -> Result<Vec<OpenWindow>, String> {
    let active = xprop(&["-root", "_NET_ACTIVE_WINDOW"])?;
    let active = active
        .split_once('#')
        .and_then(|(_, value)| parse_xid(value.trim()).ok());
    let output = xprop(&["-root", "_NET_CLIENT_LIST"])?;
    let ids = client_ids(&output)?;
    let mut windows = Vec::new();
    for wid in ids {
        let id = format!("0x{wid:x}");
        // Windows may disappear between the root query and this per-window query.
        if let Ok(info) = xprop(&[
            "-id",
            &id,
            "WM_CLASS",
            "_NET_WM_NAME",
            "WM_NAME",
            "_NET_WM_WINDOW_TYPE",
            "_NET_WM_PID",
        ]) {
            if let Some(window) = parse_window(&id, &info, active, std::process::id()) {
                windows.push(window);
            }
        }
    }
    Ok(windows)
}
/// X11 owns XID parsing, EWMH probes and native requests. The common interface
/// only passes opaque IDs and receives structured errors.
pub struct X11;
impl WindowManager for X11 {
    fn capabilities(&self) -> Result<Capabilities, WindowError> {
        capabilities().map_err(|e| WindowError::adapter("x11", "capabilities", None, e))
    }
    fn list(&self) -> Result<Vec<OpenWindow>, WindowError> {
        list().map_err(|e| WindowError::adapter("x11", "list", None, e))
    }
    fn activate(&self, id: &WindowId) -> Result<bool, WindowError> {
        activate_window(id.as_str().into()).map_err(|e| WindowError::adapter("x11", "activate", Some(id), e))
    }
    fn close(&self, id: &WindowId) -> Result<bool, WindowError> {
        close_window(id.as_str().into()).map_err(|e| WindowError::adapter("x11", "close", Some(id), e))
    }
    fn force_kill(&self, id: &WindowId) -> Result<bool, WindowError> {
        force_kill_window(id.as_str().into()).map_err(|e| WindowError::adapter("x11", "force_kill", Some(id), e))
    }
}

#[cfg(test)]
#[path = "x11_fixtures.rs"]
mod fixtures;

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn capabilities_require_current_properties_and_exact_advertised_atoms() {
        let caps = parse_capabilities("_NET_CLIENT_LIST(WINDOW): window id #\n_NET_SUPPORTED(ATOM) = _NET_ACTIVE_WINDOW, _NET_CLOSE_WINDOW, _NET_WM_NAME");
        assert!(caps.enumerate && caps.activate && caps.close);
        let partial = parse_capabilities("_NET_CLIENT_LIST(WINDOW): window id # 0x12\n_NET_SUPPORTED(ATOM) = _NET_ACTIVE_WINDOW_EXTRA, _NET_CLOSE_WINDOW");
        assert!(partial.enumerate && partial.close);
        assert!(!partial.activate);
        let absent = parse_capabilities(
            "_NET_CLIENT_LIST: not found.\n_NET_SUPPORTED: no such atom on any window.",
        );
        assert!(!absent.enumerate && !absent.activate && !absent.close);
        assert!(!parse_capabilities("_NET_CLIENT_LIST(CARDINAL) = 42").enumerate);
        assert!(!parse_capabilities("_NET_SUPPORTED(STRING) = _NET_ACTIVE_WINDOW").activate);
    }
    #[test]
    fn client_list_distinguishes_empty_unsupported_and_malformed_properties() {
        assert!(client_ids("_NET_CLIENT_LIST(WINDOW): window id #")
            .unwrap()
            .is_empty());
        assert!(client_ids("_NET_CLIENT_LIST: no such atom on any window.")
            .unwrap_err()
            .starts_with("window_manager_unsupported:"));
        assert!(client_ids("_NET_CLIENT_LIST(WINDOW): invalid")
            .unwrap_err()
            .starts_with("window_list_invalid:"));
        assert!(client_ids("_NET_CLIENT_LIST(WINDOW): window id # 0").is_err());
        assert!(client_ids("_NET_CLIENT_LIST(WINDOW): window id # 0x100000000").is_err());
    }
    #[test]
    fn actions_require_an_exact_current_managed_xid() {
        let clients = "_NET_CLIENT_LIST(WINDOW): window id # 0x00012, 0x120";
        assert_eq!(listed_xid("18", clients).unwrap(), 0x12);
        assert_eq!(listed_xid("0x120", clients).unwrap(), 0x120);
        assert!(listed_xid("0", clients).is_err());
        assert!(listed_xid("0x100000000", clients).is_err());
        assert!(listed_xid("0x2", clients).is_err());
        assert!(listed_xid("0x12", "_NET_CLIENT_LIST: not found.").is_err());
    }
    #[test]
    fn internal_filter_uses_pid_and_type_property_not_title_or_class_text() {
        let info = "WM_CLASS(STRING) = \"deskmorph\", \"Deskmorph\"\n_NET_WM_NAME(UTF8_STRING) = \"DeskMorph Studio _NET_WM_WINDOW_TYPE_DOCK\"\n_NET_WM_PID(CARDINAL) = 123\n_NET_WM_WINDOW_TYPE(ATOM) = _NET_WM_WINDOW_TYPE_NORMAL";
        assert!(parse_window("0x12", info, Some(0x12), 999).unwrap().is_active);
        assert!(parse_window("0x12", info, None, 123).is_none());
        for kind in ["_NET_WM_WINDOW_TYPE_DOCK", "_NET_WM_WINDOW_TYPE_DESKTOP"] {
            let panel = info.replace("= _NET_WM_WINDOW_TYPE_NORMAL", &format!("= _NET_WM_WINDOW_TYPE_NORMAL, {kind}"));
            assert!(parse_window("0x12", &panel, None, 999).is_none());
        }
    }
    #[test]
    fn parses_unicode_escaped_titles_and_exact_active_id() {
        let info = "WM_CLASS(STRING) = \"browser\", \"Google-Chrome\"\n_NET_WM_NAME(UTF8_STRING) = \"Tài liệu \\\"mới\\\"\"\n_NET_WM_PID(CARDINAL) = 123";
        let window = parse_window("0x00012", info, Some(0x12), 999).unwrap();
        assert_eq!(window.class_name, "Google-Chrome");
        assert_eq!(window.title, "Tài liệu \"mới\"");
        assert!(window.is_active);
        assert!(
            !parse_window("0x120", info, Some(0x12), 999)
                .unwrap()
                .is_active
        );
        assert!(parse_window("0x12", info, None, 123).is_none());
        assert!(parse_window(
            "0x12",
            "_NET_WM_WINDOW_TYPE(ATOM) = _NET_WM_WINDOW_TYPE_DOCK",
            None,
            999
        )
        .is_none());
    }
}
