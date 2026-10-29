//! Backend-independent window contract. IDs are opaque outside their adapter.
pub mod x11;
mod snapshots;
pub use snapshots::WindowSnapshots;
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(transparent)]
pub struct WindowId(String);
impl WindowId {
    pub fn as_str(&self) -> &str { &self.0 }
}
impl From<String> for WindowId {
    fn from(value: String) -> Self { Self(value) }
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct OpenWindow {
    pub id: WindowId,
    pub class_name: String,
    pub title: String,
    pub is_active: bool,
}
#[derive(Clone, Copy, Debug, Default, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Capabilities {
    pub enumerate: bool,
    pub activate: bool,
    pub close: bool,
}
#[derive(Debug, Serialize)]
pub struct WindowError {
    pub code: String,
    pub message: String,
    pub context: ErrorContext,
}
#[derive(Debug, Serialize)]
pub struct ErrorContext {
    pub backend: &'static str,
    pub operation: &'static str,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub target: Option<WindowId>,
}
impl WindowError {
    fn new(code: &str, message: &str, backend: &'static str, operation: &'static str, target: Option<&WindowId>) -> Self {
        Self { code: code.into(), message: message.into(), context: ErrorContext { backend, operation, target: target.cloned() } }
    }
    fn adapter(backend: &'static str, operation: &'static str, target: Option<&WindowId>, raw: String) -> Self {
        let (code, message) = raw.split_once(':').map(|(c, m)| (c, m.trim())).unwrap_or((&raw, &raw));
        if !code.is_empty() && code.bytes().all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || c == b'_') {
            Self::new(code, message, backend, operation, target)
        } else {
            Self::new(&format!("window_{operation}_failed"), &raw, backend, operation, target)
        }
    }
}
impl std::fmt::Display for WindowError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result { write!(f, "{}: {}", self.code, self.message) }
}
impl std::error::Error for WindowError {}

pub trait WindowManager {
    fn capabilities(&self) -> Result<Capabilities, WindowError>;
    fn list(&self) -> Result<Vec<OpenWindow>, WindowError>;
    fn activate(&self, id: &WindowId) -> Result<bool, WindowError>;
    fn close(&self, id: &WindowId) -> Result<bool, WindowError>;
    fn force_kill(&self, id: &WindowId) -> Result<bool, WindowError>;
}
fn select_backend(session: &str, display: Option<&str>) -> Result<Box<dyn WindowManager>, WindowError> {
    if session != "x11" {
        return Err(WindowError::new("window_backend_unsupported", "Quản lý cửa sổ native hiện yêu cầu X11; XWayland không bao phủ cửa sổ Wayland.", "none", "select", None));
    }
    if display.is_none_or(|value| value.trim().is_empty()) {
        return Err(WindowError::new("x11_display_missing", "Phiên X11 chưa cung cấp DISPLAY.", "x11", "select", None));
    }
    Ok(Box::new(x11::X11))
}
pub fn backend() -> Result<Box<dyn WindowManager>, WindowError> {
    select_backend(&std::env::var("XDG_SESSION_TYPE").unwrap_or_default(), std::env::var("DISPLAY").ok().as_deref())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn selection_does_not_promote_xwayland_or_missing_display_to_native_support() {
        for session in ["wayland", "", "unknown"] {
            let error = select_backend(session, Some(":0")).err().unwrap();
            assert_eq!(error.code, "window_backend_unsupported");
            assert_eq!(error.context.operation, "select");
        }
        for display in [None, Some(""), Some("  ")] {
            assert_eq!(select_backend("x11", display).err().unwrap().code, "x11_display_missing");
        }
        assert!(select_backend("x11", Some(":invalid-test")).is_ok()); // Probe remains the adapter's responsibility.
    }
    #[test]
    fn wire_ids_are_opaque_strings_and_error_context_preserves_the_target_and_operation() {
        let id: WindowId = serde_json::from_str("\"0x12\"").unwrap();
        let model = OpenWindow { id: id.clone(), class_name: "Example".into(), title: "Document".into(), is_active: true };
        assert_eq!(serde_json::to_value(model).unwrap()["id"], "0x12");
        let error = WindowError::adapter("x11", "close", Some(&id), "window_target_missing: Window closed".into());
        let wire = serde_json::to_value(error).unwrap();
        assert_eq!(wire["code"], "window_target_missing");
        assert_eq!(wire["message"], "Window closed");
        assert_eq!(wire["context"], serde_json::json!({"backend":"x11", "operation":"close", "target":"0x12"}));
        let plain = WindowError::adapter("x11", "activate", None, "Cannot connect to X11 display".into());
        assert_eq!(plain.code, "window_activate_failed");
        assert_eq!(plain.message, "Cannot connect to X11 display");
    }
}
