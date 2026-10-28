pub mod x11;
use crate::OpenWindow;

pub trait WindowManager {
    fn list(&self) -> Result<Vec<OpenWindow>, String>;
    fn activate(&self, id: String) -> Result<bool, String>;
    fn close(&self, id: String) -> Result<bool, String>;
    fn force_kill(&self, id: String) -> Result<bool, String>;
}
struct X11;
impl WindowManager for X11 {
    fn list(&self) -> Result<Vec<OpenWindow>, String> { x11::list() }
    fn activate(&self, id: String) -> Result<bool, String> { x11::activate_window(id) }
    fn close(&self, id: String) -> Result<bool, String> { x11::close_window(id) }
    fn force_kill(&self, id: String) -> Result<bool, String> { x11::force_kill_window(id) }
}
pub fn backend() -> Result<Box<dyn WindowManager>, String> {
    if std::env::var("XDG_SESSION_TYPE").unwrap_or_default() == "x11" && std::env::var_os("DISPLAY").is_some() {
        Ok(Box::new(X11))
    } else { Err("window_backend_unsupported: Quản lý cửa sổ native hiện yêu cầu phiên X11; XWayland không bao phủ cửa sổ Wayland.".into()) }
}
