//! Each scenario gets a fresh process: GLib caches XDG paths, locale and desktop.
//! Never mutate those process globals in the parallel Rust test runner.
use super::*;
use std::{fs, os::unix::fs::PermissionsExt, path::PathBuf, process::Command};

struct Fixture(PathBuf);
impl Fixture {
    fn new(scenario: &str) -> Self {
        let stamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let root = std::env::temp_dir().join(format!(
            "deskmorph-apps-{}-{scenario}-{stamp}",
            std::process::id()
        ));
        for directory in [
            "user/applications",
            "system/applications",
            "fallback/applications",
            "bin",
            "config",
            "cache",
        ] {
            fs::create_dir_all(root.join(directory)).unwrap();
        }
        Self(root)
    }
    fn entry(&self, directory: &str, id: &str, body: &str) {
        let path = self.0.join(directory).join("applications").join(id);
        fs::create_dir_all(path.parent().unwrap()).unwrap();
        fs::write(
            path,
            format!("[Desktop Entry]\nType=Application\nName=Fixture\nExec=/bin/true\n{body}"),
        )
        .unwrap();
    }
    fn script(&self, name: &str, body: &str) -> PathBuf {
        let path = self.0.join("bin").join(name);
        fs::write(&path, format!("#!/bin/sh\n{body}\n")).unwrap();
        fs::set_permissions(&path, fs::Permissions::from_mode(0o700)).unwrap();
        path
    }
    fn run(&self, scenario: &str) {
        let executable = std::env::current_exe().unwrap();
        let mut command = if scenario == "dbus" {
            let mut command = Command::new("/usr/bin/dbus-run-session");
            command
                .args(["--dbus-daemon=/usr/bin/dbus-daemon", "--"])
                .arg(&executable);
            command
        } else {
            Command::new(&executable)
        };
        command
            .args([
                "--exact",
                "applications::fixtures::isolated_child",
                "--nocapture",
            ])
            .env("DESKMORPH_APP_FIXTURE", &self.0)
            .env("DESKMORPH_APP_SCENARIO", scenario)
            .env("HOME", &self.0)
            .env("XDG_CONFIG_HOME", self.0.join("config"))
            .env("XDG_CACHE_HOME", self.0.join("cache"))
            .env("XDG_DATA_HOME", self.0.join("user"))
            .env(
                "XDG_DATA_DIRS",
                format!(
                    "{}:{}",
                    self.0.join("system").display(),
                    self.0.join("fallback").display()
                ),
            )
            .env("XDG_CURRENT_DESKTOP", "GNOME")
            .env("LANGUAGE", "fr")
            .env("LANG", "C.UTF-8")
            .env("LC_ALL", "C.UTF-8")
            .env("PATH", self.0.join("bin"))
            // No fixture can activate applications on the user's real session bus.
            .env(
                "DBUS_SESSION_BUS_ADDRESS",
                format!("unix:path={}/absent-bus", self.0.display()),
            );
        let output = command.output().unwrap();
        assert!(
            output.status.success(),
            "{scenario}:\n{}\n{}",
            String::from_utf8_lossy(&output.stdout),
            String::from_utf8_lossy(&output.stderr)
        );
    }
}
impl Drop for Fixture {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}

#[test]
fn xdg_precedence_hidden_overrides_locale_and_desktop_filters() {
    let f = Fixture::new("catalogue");
    f.entry("system", "override.desktop", "Name=System");
    f.entry("fallback", "override.desktop", "Name=Fallback");
    f.entry("user", "override.desktop", "Name=User");
    f.entry("system", "masked.desktop", "Name=Must not leak");
    f.entry("user", "masked.desktop", "Hidden=true");
    f.entry("system", "nested/example.desktop", "Name=Nested");
    f.entry("user", "locale.desktop", "Name=English\nName[fr]=Éditeur\nGenericName=Editor\nGenericName[fr]=Texte\nKeywords=code;edit;\nKeywords[fr]=texte;édition;\nStartupWMClass=FixtureClass\nIcon=nonexistent-deskmorph-icon\nActions=New;\n[Desktop Action New]\nName=New\nName[fr]=Nouveau\nExec=/bin/true");
    for (id, body) in [
        ("only.desktop", "OnlyShowIn=GNOME;"),
        ("other.desktop", "OnlyShowIn=KDE;"),
        ("not.desktop", "NotShowIn=GNOME;"),
        ("nodisplay.desktop", "NoDisplay=true"),
        (
            "missing-exec.desktop",
            "TryExec=deskmorph-nonexistent-fixture",
        ),
        ("present-exec.desktop", "TryExec=fixture-present"),
        (
            "wrong-type.desktop",
            "Type=Link\nURL=https://example.invalid",
        ),
    ] {
        f.entry("user", id, body);
    }
    f.script("fixture-present", "exit 0");
    fs::write(
        f.0.join("user/applications/broken.desktop"),
        "This is not a desktop entry",
    )
    .unwrap();
    f.run("catalogue");
}

#[test]
fn desktop_launch_preserves_arguments_actions_terminal_and_reports_missing_app() {
    let f = Fixture::new("launch");
    let executable = f.script(
        "fixture app",
        "printf '%s\\n' \"$@\" > \"$DESKMORPH_APP_FIXTURE/argv\"",
    );
    let exec = crate::registration::quote_exec(&executable).unwrap();
    f.entry("user", "launch.desktop", &format!("Name=Launch Fixture\nIcon=fixture-icon\nExec={exec} \"literal ; $(touch never)\" %% %c %k %i %f %u %F %U\nActions=New;\n[Desktop Action New]\nName=New\nExec={exec} action"));
    f.entry(
        "user",
        "terminal.desktop",
        &format!("Exec={exec} terminal\nTerminal=true"),
    );
    f.entry("user", "hidden.desktop", "Hidden=true");
    f.entry("user", "nodisplay.desktop", "NoDisplay=true");
    f.entry("user", "removed.desktop", "");
    // GIO's terminal fallback receives argv, never a shell command string.
    f.script("xterm", "printf '%s\\n' \"$@\" > \"$DESKMORPH_APP_FIXTURE/terminal-argv\"\n[ \"$1\" = '-e' ] && shift\nexec \"$@\"");
    f.run("launch");
}

#[test]
fn retained_app_monitor_observes_install_and_removal_and_disconnects_on_drop() {
    let f = Fixture::new("monitor");
    f.entry("user", "existing.desktop", "");
    f.run("monitor");
}

#[test]
#[ignore = "requires private Unix D-Bus socket; run with --include-ignored outside restricted sandbox"]
fn dbus_activatable_entry_activates_private_service_instead_of_exec() {
    let f = Fixture::new("dbus");
    let fallback = f.script(
        "fallback",
        "printf fallback > \"$DESKMORPH_APP_FIXTURE/fallback-invoked\"",
    );
    f.entry(
        "user",
        "org.deskmorph.Fixture.desktop",
        &format!(
            "Exec={}\nDBusActivatable=true",
            crate::registration::quote_exec(&fallback).unwrap()
        ),
    );
    let services = f.0.join("user/dbus-1/services");
    fs::create_dir_all(&services).unwrap();
    let executable = std::env::current_exe().unwrap();
    fs::write(services.join("org.deskmorph.Fixture.service"), format!(
        "[D-BUS Service]\nName=org.deskmorph.Fixture\nExec={} --exact applications::fixtures::dbus_application_service --nocapture\n",
        gio::glib::shell_quote(executable.to_str().unwrap()).to_string_lossy(),
    )).unwrap();
    f.run("dbus");
}

#[test]
fn dbus_application_service() {
    use gio::glib::variant::ToVariant;
    let Some(root) = std::env::var_os("DESKMORPH_APP_FIXTURE").map(PathBuf::from) else {
        return;
    };
    if std::env::var("DESKMORPH_APP_SCENARIO").as_deref() != Ok("dbus") {
        return;
    }
    let connection = gio::bus_get_sync(gio::BusType::Session, gio::Cancellable::NONE).unwrap();
    let interface = gio::DBusNodeInfo::for_xml("<node><interface name='org.freedesktop.Application'><method name='Activate'><arg type='a{sv}' direction='in'/></method></interface></node>").unwrap().lookup_interface("org.freedesktop.Application").unwrap();
    let main_loop = gio::glib::MainLoop::new(None, false);
    let done = main_loop.clone();
    let marker = root.join("activated");
    let registration = connection
        .register_object(
            "/org/deskmorph/Fixture",
            &interface,
            move |_, _, _, _, method, _, invocation| {
                fs::write(&marker, method).unwrap();
                invocation.return_value(Some(&().to_variant()));
                done.quit();
            },
            |_, _, _, _, _| ().to_variant(),
            |_, _, _, _, _, _| false,
        )
        .unwrap();
    connection
        .call_sync(
            Some("org.freedesktop.DBus"),
            "/org/freedesktop/DBus",
            "org.freedesktop.DBus",
            "RequestName",
            Some(&("org.deskmorph.Fixture", 0u32).to_variant()),
            None,
            gio::DBusCallFlags::NONE,
            3000,
            gio::Cancellable::NONE,
        )
        .unwrap();
    let expired = main_loop.clone();
    let timeout = gio::glib::timeout_add_local_once(Duration::from_secs(5), move || expired.quit());
    main_loop.run();
    if root.join("activated").exists() {
        timeout.remove();
    }
    connection.flush_sync(gio::Cancellable::NONE).unwrap();
    connection.unregister_object(registration).unwrap();
    assert_eq!(
        fs::read_to_string(root.join("activated")).unwrap(),
        "Activate"
    );
    fs::write(root.join("service-done"), "ok").unwrap();
}

fn wait_file(root: &Path, name: &str) -> String {
    for _ in 0..200 {
        if let Ok(text) = fs::read_to_string(root.join(name)) {
            if !text.is_empty() {
                return text;
            }
        }
        std::thread::sleep(Duration::from_millis(10));
    }
    panic!("fixture did not write {name}");
}

#[test]
fn isolated_child() {
    let Some(root) = std::env::var_os("DESKMORPH_APP_FIXTURE").map(PathBuf::from) else {
        return;
    };
    match std::env::var("DESKMORPH_APP_SCENARIO").unwrap().as_str() {
        "catalogue" => {
            let apps: Vec<_> = gio::AppInfo::all()
                .into_iter()
                .filter_map(|a| a.downcast::<gio::DesktopAppInfo>().ok())
                .collect();
            let named = |id: &str| apps.iter().find(|a| a.id().as_deref() == Some(id)).unwrap();
            assert_eq!(named("override.desktop").name(), "User");
            assert_eq!(
                apps.iter()
                    .filter(|a| a.id().as_deref() == Some("override.desktop"))
                    .count(),
                1
            );
            assert_eq!(named("nested-example.desktop").name(), "Nested");
            assert!(named("only.desktop").should_show());
            assert!(named("present-exec.desktop").should_show());
            for id in [
                "masked.desktop",
                "other.desktop",
                "not.desktop",
                "nodisplay.desktop",
                "missing-exec.desktop",
                "wrong-type.desktop",
                "broken.desktop",
            ] {
                assert!(
                    !apps.iter().any(|a| a.id().as_deref() == Some(id)
                        && !a.is_hidden()
                        && a.should_show()),
                    "{id} leaked into catalogue"
                );
                if let Some(app) = apps.iter().find(|a| a.id().as_deref() == Some(id)) {
                    assert!(describe_with_icon(app.clone(), |_| None).is_none());
                }
            }
            let localized = named("locale.desktop");
            assert_eq!(localized.name(), "Éditeur");
            assert_eq!(localized.generic_name().unwrap(), "Texte");
            assert_eq!(localized.keywords(), ["texte", "édition"]);
            assert_eq!(localized.action_name("New"), "Nouveau");
            assert_eq!(localized.startup_wm_class().unwrap(), "FixtureClass");
            let model = describe_with_icon(localized.clone(), |_| None).unwrap();
            assert_eq!(model.id, "locale.desktop");
            assert_eq!(model.name, "Éditeur");
            assert_eq!(model.generic_name, "Texte");
            assert_eq!(model.keywords, ["texte", "édition"]);
            assert_eq!(model.executable, "/bin/true");
            assert_eq!(model.match_classes, ["fixtureclass", "locale", "true"]);
            assert!(
                model.icon_path.is_none(),
                "missing icon keeps the app available for UI fallback"
            );
            assert_eq!(model.actions[0].id, "New");
            assert_eq!(model.actions[0].name, "Nouveau");
        }
        "launch" => {
            // GIO treats a Hidden tombstone as an absent desktop ID.
            assert!(launch_desktop_entry("hidden.desktop", None)
                .unwrap_err()
                .starts_with("app_missing:"));
            assert!(launch_desktop_entry("nodisplay.desktop", None)
                .unwrap_err()
                .starts_with("app_hidden:"));
            assert!(launch_desktop_entry("launch.desktop", Some("Absent"))
                .unwrap_err()
                .starts_with("app_action_missing:"));
            fs::remove_file(root.join("user/applications/removed.desktop")).unwrap();
            assert!(launch_desktop_entry("removed.desktop", None)
                .unwrap_err()
                .starts_with("app_missing:"));
            launch_desktop_entry("launch.desktop", None).unwrap();
            let argv = wait_file(&root, "argv");
            let args: Vec<_> = argv.lines().collect();
            assert_eq!(
                &args[..3],
                ["literal ; $(touch never)", "%", "Launch Fixture"]
            );
            assert_eq!(
                args[3],
                root.join("user/applications/launch.desktop")
                    .to_str()
                    .unwrap()
            );
            assert_eq!(&args[4..], ["--icon", "fixture-icon"]);
            assert!(!root.join("never").exists());
            fs::remove_file(root.join("argv")).unwrap();
            launch_desktop_entry("launch.desktop", Some("New")).unwrap();
            assert_eq!(wait_file(&root, "argv"), "action\n");
            fs::remove_file(root.join("argv")).unwrap();
            launch_desktop_entry("terminal.desktop", None).unwrap();
            assert_eq!(wait_file(&root, "argv"), "terminal\n");
            let terminal = wait_file(&root, "terminal-argv");
            assert!(terminal.starts_with("-e\n"));
            assert!(terminal.contains("fixture app\nterminal\n"));
        }
        "dbus" => {
            launch_desktop_entry("org.deskmorph.Fixture.desktop", None).unwrap();
            let context = gio::glib::MainContext::default();
            for _ in 0..500 {
                while context.pending() {
                    context.iteration(false);
                }
                if root.join("service-done").exists() {
                    break;
                }
                std::thread::sleep(Duration::from_millis(10));
            }
            assert_eq!(
                fs::read_to_string(root.join("activated")).unwrap(),
                "Activate"
            );
            assert!(root.join("service-done").exists());
            assert!(
                !root.join("fallback-invoked").exists(),
                "DBus activation must not run Exec"
            );
        }
        "monitor" => {
            use std::{cell::Cell, rc::Rc};
            let changes = Rc::new(Cell::new(0));
            let counter = changes.clone();
            let watch = AppInfoWatch::new(move || counter.set(counter.get() + 1));
            let _ = gio::AppInfo::all();
            let entry = root.join("user/applications/new.desktop");
            fs::write(
                &entry,
                "[Desktop Entry]\nType=Application\nName=New Fixture\nExec=/bin/true\n",
            )
            .unwrap();
            let context = gio::glib::MainContext::default();
            let wait_change = |previous| {
                for _ in 0..500 {
                    while context.pending() {
                        context.iteration(false);
                    }
                    if changes.get() > previous {
                        return;
                    }
                    std::thread::sleep(Duration::from_millis(10));
                }
                panic!("GIO catalogue monitor did not observe change");
            };
            wait_change(0);
            assert!(gio::AppInfo::all()
                .iter()
                .any(|a| a.id().as_deref() == Some("new.desktop")));
            let previous = changes.get();
            fs::remove_file(&entry).unwrap();
            wait_change(previous);
            assert!(!gio::AppInfo::all()
                .iter()
                .any(|a| a.id().as_deref() == Some("new.desktop")));
            let monitor = watch.monitor.clone();
            drop(watch);
            let previous = changes.get();
            monitor.emit_by_name::<()>("changed", &[]);
            assert_eq!(
                changes.get(),
                previous,
                "dropped watch must disconnect its callback"
            );
        }
        unknown => panic!("unknown fixture scenario: {unknown}"),
    }
}
