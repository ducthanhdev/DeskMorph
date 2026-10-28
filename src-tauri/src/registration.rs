use std::{fs, path::{Path, PathBuf}};

pub fn xdg_dir(variable: &str, fallback: &str) -> Result<PathBuf, String> {
    if let Some(path) = std::env::var_os(variable).filter(|p| Path::new(p).is_absolute()) { return Ok(path.into()); }
    std::env::var_os("HOME").map(|home| PathBuf::from(home).join(fallback)).ok_or_else(|| "Không tìm thấy thư mục người dùng".into())
}
/// App-only profile override. Unlike XDG_CONFIG_HOME this leaves desktop
/// service settings (notably dconf/GSettings) in the active user's namespace.
pub fn config_root() -> Result<PathBuf, String> {
    match std::env::var_os("DESKMORPH_CONFIG_HOME") {
        Some(path) if Path::new(&path).is_absolute() => Ok(path.into()),
        Some(_) => Err("DESKMORPH_CONFIG_HOME phải là đường dẫn tuyệt đối".into()),
        None => xdg_dir("XDG_CONFIG_HOME", ".config"),
    }
}
pub fn autostart_file() -> Result<PathBuf, String> { Ok(config_root()?.join("autostart/deskmorph.desktop")) }
pub fn application_file() -> Result<PathBuf, String> { Ok(xdg_dir("XDG_DATA_HOME", ".local/share")?.join("applications/deskmorph.desktop")) }
pub fn quote_exec(path: &Path) -> Result<String, String> {
    let text = path.to_str().ok_or("Đường dẫn executable không phải UTF-8")?;
    if text.contains(['\n', '\r', '\0']) { return Err("Đường dẫn executable chứa ký tự không được hỗ trợ".into()); }
    let mut quoted = String::from("\"");
    // First desktop-entry value unescaping, then Exec argument unescaping.
    for c in text.chars() {
        match c {
            '\\' => quoted.push_str("\\\\\\\\"),
            '"' => { quoted.push_str("\\\\"); quoted.push('"'); },
            '$' | '`' => { quoted.push_str("\\\\"); quoted.push(c); }
            '%' => quoted.push_str("%%"),
            c => quoted.push(c),
        }
    }
    quoted.push('"');
    Ok(quoted)
}
pub fn entry(executable: &Path, autostart: bool) -> Result<String, String> {
    let command = quote_exec(executable)?;
    Ok(format!("[Desktop Entry]\nType=Application\nName=DeskMorph\nComment=Desktop customization studio and Dock\nExec=env WEBKIT_DISABLE_DMABUF_RENDERER=1 {command}\nIcon=preferences-desktop-theme\nCategories=Utility;Settings;\nTerminal=false\nStartupNotify=false\n{}", if autostart { "X-GNOME-Autostart-enabled=true\n" } else { "" }))
}
pub fn install(path: &Path, autostart: bool) -> Result<(), String> {
    let executable = std::env::current_exe().map_err(|e| e.to_string())?;
    let content = entry(&executable, autostart)?;
    fs::create_dir_all(path.parent().ok_or("Thiếu thư mục desktop entry")?).map_err(|e| e.to_string())?;
    fs::write(path, content).map_err(|e| e.to_string())
}
#[cfg(test)]
mod tests {
    use super::*;
    use gio::prelude::*;
    use std::os::unix::fs::PermissionsExt;
    #[test]
    fn desktop_entry_launches_paths_with_spaces_quotes_percent_and_shell_characters() {
        let dir = std::env::temp_dir().join(format!("deskmorph-entry-{}", std::process::id()));
        fs::create_dir_all(&dir).unwrap();
        let executable = dir.join("app space \" $HOME `name` \\ 100%");
        let marker = dir.join("launched");
        fs::write(&executable, format!("#!/bin/sh\nprintf ok > '{}'\n", marker.display())).unwrap();
        fs::set_permissions(&executable, fs::Permissions::from_mode(0o700)).unwrap();
        let desktop = dir.join("test.desktop");
        fs::write(&desktop, entry(&executable, false).unwrap()).unwrap();
        let app = gio::DesktopAppInfo::from_filename(&desktop).expect("GIO must parse generated entry");
        app.launch(&[], None::<&gio::AppLaunchContext>).unwrap();
        for _ in 0..50 { if marker.exists() { break; } std::thread::sleep(std::time::Duration::from_millis(10)); }
        assert_eq!(fs::read_to_string(&marker).unwrap(), "ok");
        fs::remove_dir_all(dir).unwrap();
    }
}
