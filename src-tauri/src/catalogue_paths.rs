//! Prepare GIO's shared discovery/launch search path before GLib caches it.
use std::{
    ffi::{OsStr, OsString},
    path::{Path, PathBuf},
};

pub(crate) fn data_dirs(
    configured: Option<&OsStr>,
    exports: &[PathBuf],
) -> Result<OsString, std::env::JoinPathsError> {
    let defaults = OsStr::new("/usr/local/share:/usr/share");
    let configured = configured
        .filter(|value| !value.is_empty())
        .unwrap_or(defaults);
    let mut paths = Vec::new();
    for path in std::env::split_paths(configured).filter(|path| path.is_absolute()) {
        if !paths.contains(&path) {
            paths.push(path);
        }
    }
    if paths.is_empty() {
        paths.extend(std::env::split_paths(defaults));
    }
    for path in exports {
        // Keep explicitly configured order authoritative. Extra exports are
        // fallbacks, and cannot displace XDG_DATA_HOME's desktop-ID overrides.
        // Keep absent roots: GIO can watch their ancestors and discover the
        // first installation without mutating cached process paths later.
        if path.is_absolute() && !paths.contains(path) && std::env::join_paths([path]).is_ok() {
            paths.push(path.clone());
        }
    }
    std::env::join_paths(paths)
}

fn absolute(value: Option<OsString>) -> Option<PathBuf> {
    value.map(PathBuf::from).filter(|path| path.is_absolute())
}

/// Call only during single-threaded startup, before GTK/GIO or worker creation.
pub fn prepare() -> Result<(), String> {
    let data_home = absolute(std::env::var_os("XDG_DATA_HOME"))
        .or_else(|| absolute(std::env::var_os("HOME")).map(|home| home.join(".local/share")));
    let user_flatpak = absolute(std::env::var_os("FLATPAK_USER_DIR"))
        .or_else(|| data_home.map(|home| home.join("flatpak")));
    let mut exports: Vec<_> = user_flatpak
        .into_iter()
        .map(|root| root.join("exports/share"))
        .collect();
    exports.extend([
        Path::new("/var/lib/flatpak/exports/share").to_path_buf(),
        Path::new("/var/lib/snapd/desktop").to_path_buf(),
    ]);
    let current = std::env::var_os("XDG_DATA_DIRS");
    let dirs = data_dirs(current.as_deref(), &exports)
        .map_err(|error| format!("catalogue_data_dirs: {error}"))?;
    if current.as_ref() != Some(&dirs) {
        std::env::set_var("XDG_DATA_DIRS", dirs);
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn empty_or_relative_xdg_dirs_use_spec_defaults() {
        for value in [
            None,
            Some(OsStr::new("")),
            Some(OsStr::new("relative::another")),
        ] {
            assert_eq!(
                data_dirs(value, &[]).unwrap(),
                "/usr/local/share:/usr/share"
            );
        }
        assert_eq!(
            data_dirs(Some(OsStr::new("/custom:/usr/share:/custom:relative")), &[]).unwrap(),
            "/custom:/usr/share"
        );
    }
}
