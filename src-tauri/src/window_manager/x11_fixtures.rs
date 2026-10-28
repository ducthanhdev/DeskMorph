//! Exercise process/adapter failures without accessing an X server or changing
//! the test runner's global environment.
use super::*;
use std::{fs, os::unix::fs::PermissionsExt, path::PathBuf};

#[test]
fn xprop_errors_and_unsupported_wm_are_not_successful_empty_lists() {
    let root = std::env::temp_dir().join(format!("deskmorph-xprop-{}", std::process::id()));
    fs::create_dir_all(&root).unwrap();
    struct Cleanup(PathBuf);
    impl Drop for Cleanup {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.0);
        }
    }
    let _cleanup = Cleanup(root.clone());
    for (scenario, body) in [
        ("failed", "printf 'fixture display unavailable' >&2\nexit 13"),
        ("unsupported", "printf '%s\\n' '_NET_CLIENT_LIST: no such atom on any window.'"),
        ("malformed", "printf '%s\\n' '_NET_CLIENT_LIST(WINDOW): malformed'"),
        ("empty", "printf '%s\\n' '_NET_CLIENT_LIST(WINDOW): window id #' '_NET_SUPPORTED(ATOM) = _NET_ACTIVE_WINDOW, _NET_CLOSE_WINDOW'"),
        ("unsupported-action", "printf '%s\\n' '_NET_CLIENT_LIST(WINDOW): window id #' '_NET_SUPPORTED(ATOM) = _NET_ACTIVE_WINDOW_EXTRA'"),
        ("missing", ""),
    ] {
        let directory = root.join(scenario);
        fs::create_dir_all(&directory).unwrap();
        if scenario != "missing" {
            let command = directory.join("xprop");
            fs::write(&command, format!("#!/bin/sh\n{body}\n")).unwrap();
            fs::set_permissions(command, fs::Permissions::from_mode(0o700)).unwrap();
        }
        let output = Command::new(std::env::current_exe().unwrap())
            .args(["--exact", "window_manager::x11::fixtures::isolated_adapter_child", "--nocapture"])
            .env("DESKMORPH_XPROP_SCENARIO", scenario).env("PATH", &directory)
            .env("DISPLAY", ":invalid-fixture").output().unwrap();
        assert!(output.status.success(), "{scenario}: {}\n{}", String::from_utf8_lossy(&output.stdout), String::from_utf8_lossy(&output.stderr));
    }
}

#[test]
fn isolated_adapter_child() {
    let Ok(scenario) = std::env::var("DESKMORPH_XPROP_SCENARIO") else {
        return;
    };
    match scenario.as_str() {
        "failed" => {
            let error = list()
                .err()
                .expect("nonzero xprop exit must fail enumeration");
            assert!(error.starts_with("xprop_failed:"));
            assert!(error.contains("fixture display unavailable"));
            assert!(capabilities().unwrap_err().starts_with("xprop_failed:"));
        }
        "missing" => {
            assert!(list().err().unwrap().starts_with("xprop_unavailable:"));
            assert!(capabilities()
                .unwrap_err()
                .starts_with("xprop_unavailable:"));
        }
        "unsupported" => {
            assert!(list()
                .err()
                .unwrap()
                .starts_with("window_manager_unsupported:"));
            assert!(!capabilities().unwrap().enumerate);
        }
        "malformed" => {
            assert!(list().err().unwrap().starts_with("window_list_invalid:"));
            assert!(!capabilities().unwrap().enumerate);
        }
        "empty" => {
            assert!(list().unwrap().is_empty());
            let caps = capabilities().unwrap();
            assert!(caps.enumerate && caps.activate && caps.close);
        }
        "unsupported-action" => {
            assert!(activate_window("0x12".into())
                .unwrap_err()
                .starts_with("window_action_unsupported:"));
            assert!(close_window("0x12".into())
                .unwrap_err()
                .starts_with("window_action_unsupported:"));
        }
        _ => panic!("unknown scenario: {scenario}"),
    }
}
