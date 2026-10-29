//! Fresh-process fixtures: GLib caches user directories and MIME associations.
use super::*;
use std::{fs, path::PathBuf, os::unix::fs::PermissionsExt, process::Command};

struct Fixture(PathBuf);
impl Fixture {
    fn new() -> Self {
        let stamp = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos();
        let root = std::env::temp_dir().join(format!("deskmorph-system-{}-{stamp}", std::process::id()));
        for directory in ["data/applications", "config", "cache", "system", "bin"] {
            fs::create_dir_all(root.join(directory)).unwrap();
        }
        Self(root)
    }
    fn run(&self, scenario: &str) {
        let output = Command::new(std::env::current_exe().unwrap())
            .args(["--exact", "system_widgets::fixtures::isolated_child", "--nocapture"])
            .env("DESKMORPH_SYSTEM_FIXTURE", &self.0).env("DESKMORPH_SYSTEM_SCENARIO", scenario)
            .env("HOME", &self.0).env("XDG_CONFIG_HOME", self.0.join("config"))
            .env("XDG_DATA_HOME", self.0.join("data")).env("XDG_CACHE_HOME", self.0.join("cache"))
            .env("XDG_DATA_DIRS", self.0.join("system")).env("XDG_CONFIG_DIRS", self.0.join("system"))
            .env("XDG_CURRENT_DESKTOP", "GNOME").env("PATH", self.0.join("bin"))
            .env("DBUS_SESSION_BUS_ADDRESS", format!("unix:path={}/absent-bus", self.0.display()))
            .output().unwrap();
        assert!(output.status.success(), "{scenario}:\n{}\n{}", String::from_utf8_lossy(&output.stdout), String::from_utf8_lossy(&output.stderr));
    }
}
impl Drop for Fixture { fn drop(&mut self) { let _ = fs::remove_dir_all(&self.0); } }

#[test]
fn monitor_priority_fallback_launch_rejection_and_missing_are_real_gio_results() {
    for scenario in ["monitor-preferred", "monitor-hidden", "monitor-fallback", "monitor-missing", "monitor-failed"] {
        Fixture::new().run(scenario);
    }
}
#[test]
fn downloads_respects_xdg_paths_missing_directories_and_file_manager_selection() {
    for scenario in ["downloads-custom", "downloads-missing", "downloads-no-manager", "downloads-cosmic"] {
        Fixture::new().run(scenario);
    }
}
#[test]
fn trash_uses_registered_uri_handler_and_missing_handler_is_unsupported() {
    for scenario in ["trash-present", "trash-hidden", "trash-missing"] { Fixture::new().run(scenario); }
}

#[test]
fn isolated_child() {
    let Some(root) = std::env::var_os("DESKMORPH_SYSTEM_FIXTURE").map(PathBuf::from) else { return; };
    let scenario = std::env::var("DESKMORPH_SYSTEM_SCENARIO").unwrap();
    let script = root.join("bin/record argv");
    fs::write(&script, "#!/usr/bin/python3\nimport json,os,sys\nfrom pathlib import Path\nPath(os.environ['DESKMORPH_SYSTEM_FIXTURE']).joinpath('argv.json').write_text(json.dumps(sys.argv[1:]))\n").unwrap();
    fs::set_permissions(&script, fs::Permissions::from_mode(0o700)).unwrap();
    let quoted = crate::registration::quote_exec(&script).unwrap();
    let entry = |id: &str, body: &str| {
        fs::write(root.join("data/applications").join(id), format!("[Desktop Entry]\nType=Application\nName=System fixture\n{body}\n")).unwrap();
    };
    let read_argv = || -> Vec<String> {
        let marker = root.join("argv.json");
        let deadline = Instant::now() + Duration::from_secs(5);
        loop {
            if let Ok(bytes) = fs::read(&marker) {
                if let Ok(argv) = serde_json::from_slice(&bytes) { return argv; }
            }
            assert!(Instant::now() < deadline, "No fixture launch marker");
            std::thread::sleep(Duration::from_millis(20));
        }
    };
    if scenario.starts_with("monitor-") {
        let preferred = "org.gnome.SystemMonitor.desktop";
        let fallback = "org.kde.plasma-systemmonitor.desktop";
        if scenario != "monitor-missing" {
            // A terminal-required entry with no terminal in the private PATH
            // produces a synchronous GIO rejection (not a later child exit).
            entry(preferred, &format!("Exec={quoted} preferred\nHidden={}\nTerminal={}",
                scenario == "monitor-hidden", matches!(scenario.as_str(), "monitor-fallback" | "monitor-failed")));
        }
        if matches!(scenario.as_str(), "monitor-preferred" | "monitor-hidden" | "monitor-fallback") {
            entry(fallback, &format!("Exec={quoted} fallback"));
        }
        if scenario == "monitor-missing" {
            assert!(monitor_ids().is_empty());
            assert_eq!(open_location("monitor").unwrap_err(), "system_monitor_missing");
            assert!(!root.join("argv.json").exists());
        } else if scenario == "monitor-failed" {
            let error = open_location("monitor").unwrap_err();
            assert!(error.starts_with("system_monitor_launch_failed:"));
            assert!(error.contains(preferred)); assert!(!root.join("argv.json").exists());
        } else {
            let ids = monitor_ids();
            assert_eq!(ids[0], if scenario == "monitor-hidden" { fallback } else { preferred });
            open_location("monitor").unwrap();
            assert_eq!(read_argv(), [if scenario == "monitor-preferred" { "preferred" } else { "fallback" }]);
        }
        return;
    }
    let downloads = root.join("Downloaded files ; $(touch never)");
    if scenario != "downloads-missing" { fs::create_dir(&downloads).unwrap(); }
    fs::write(root.join("config/user-dirs.dirs"), "XDG_DOWNLOAD_DIR=\"$HOME/Downloaded files ; $(touch never)\"\n").unwrap();
    if scenario.starts_with("downloads-") {
        if !matches!(scenario.as_str(), "downloads-no-manager") {
            let id = if scenario == "downloads-cosmic" { "com.system76.CosmicFiles.desktop" } else { "fixture.files.desktop" };
            entry(id, &format!("Exec={quoted} --profile \"two words\" %U\nCategories=System;FileManager;\nMimeType=inode/directory;"));
            // A default that handles inode/directory but is not a file manager
            // must not steal the open action (e.g. a disk usage analyser).
            entry("fixture.analyser.desktop", "Exec=/bin/false\nCategories=System;\nMimeType=inode/directory;");
            fs::write(root.join("config/mimeapps.list"), "[Default Applications]\ninode/directory=fixture.analyser.desktop;\n").unwrap();
            assert_eq!(folder_app().unwrap().id().as_deref(), Some(id));
        }
        if scenario == "downloads-missing" {
            assert_eq!(open_location("downloads").unwrap_err(), "downloads_missing");
            assert!(!downloads.exists()); assert!(!root.join("argv.json").exists());
        } else if scenario == "downloads-no-manager" {
            assert_eq!(open_location("downloads").unwrap_err(), "file_manager_missing");
        } else {
            open_location("downloads").unwrap();
            let argv = read_argv(); assert_eq!(argv.len(), 3);
            assert_eq!(&argv[..2], ["--profile", "two words"]);
            if scenario == "downloads-cosmic" {
                assert_eq!(argv[2], downloads.to_string_lossy());
            } else {
                // GIO may optimize a local file URI into a native path even
                // for %U. Both must designate the exact XDG directory.
                let actual = if argv[2].starts_with("file://") { gio::File::for_uri(&argv[2]).path().unwrap() }
                    else { PathBuf::from(&argv[2]) };
                assert_eq!(actual, downloads);
            }
            assert!(!root.join("never").exists(), "No path may be interpreted as shell code");
        }
    } else {
        let trash_file = root.join("data/Trash/files/sentinel.txt");
        fs::create_dir_all(trash_file.parent().unwrap()).unwrap();
        fs::write(&trash_file, "preserve trash contents").unwrap();
        if matches!(scenario.as_str(), "trash-present" | "trash-hidden") {
            entry("fixture.trash.desktop", &format!("Exec={quoted} %U\nMimeType=x-scheme-handler/trash;\nNoDisplay=true\nHidden={}", scenario == "trash-hidden"));
            fs::write(root.join("config/mimeapps.list"), "[Default Applications]\nx-scheme-handler/trash=fixture.trash.desktop;\n").unwrap();
            assert!(gio::AppInfo::default_for_uri_scheme("trash").is_some());
            if scenario == "trash-hidden" {
                assert!(trash_app().is_none());
                assert_eq!(open_location("trash").unwrap_err(), "trash_unsupported");
                assert!(!root.join("argv.json").exists());
            } else {
                assert!(trash_app().is_some(), "NoDisplay URI handlers are valid");
                open_location("trash").unwrap();
                assert_eq!(read_argv(), ["trash:///"]);
            }
        } else {
            assert_eq!(scenario, "trash-missing");
            assert!(gio::AppInfo::default_for_uri_scheme("trash").is_none());
            assert_eq!(open_location("trash").unwrap_err(), "trash_unsupported");
            assert!(!root.join("argv.json").exists());
        }
        assert_eq!(fs::read_to_string(&trash_file).unwrap(), "preserve trash contents");
    }
    assert_eq!(open_location("other").unwrap_err(), "system_location_invalid");
}
