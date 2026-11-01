mod ui_messages;
mod accessibility;
mod diagnostics;
mod shortcuts;
mod system_widgets;
mod media;
mod audio;
mod wallpaper;
mod cosmic_background;
mod cosmic_profile;
mod tooltip;
mod layout;
mod applications;
mod application_icons;
mod catalogue_paths;
mod instance;
mod registration;
mod window_manager;
mod platform;
mod displays;
mod geometry;
mod popup;
mod config;
use serde::{Deserialize, Serialize};
use std::fs;
use std::process::Command;
use std::sync::Mutex;
use sysinfo::System;
use tauri::{AppHandle, Manager};
use window_manager::{OpenWindow, WindowError, WindowId};


#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct SystemStats {
    pub cpu_usage: f32,
    pub ram_used_mb: u64,
    pub ram_total_mb: u64,
    pub ram_percent: f32,
}

pub struct AppState {
    pub sys: Mutex<SystemSampler>,
}

pub struct SystemSampler {
    sys: System,
    last: Option<(std::time::Instant, SystemStats)>,
}

#[tauri::command]
fn get_system_stats(state: tauri::State<AppState>) -> Result<SystemStats, String> {
    let _trace = diagnostics::command("get_system_stats");
    let mut sampler = state.sys.lock().map_err(|e| e.to_string())?;
    if let Some((at, stats)) = &sampler.last {
        if at.elapsed() < std::time::Duration::from_secs(2) { return Ok(stats.clone()); }
    }
    let _sample_trace = diagnostics::command("sample_system_stats");
    let sys = &mut sampler.sys;
    sys.refresh_cpu_all();
    sys.refresh_memory();

    let cpus = sys.cpus();
    let cpu_usage: f32 = if !cpus.is_empty() {
        cpus.iter().map(|c| c.cpu_usage()).sum::<f32>() / (cpus.len() as f32)
    } else {
        0.0
    };

    let total_ram = sys.total_memory() / (1024 * 1024);
    let used_ram = sys.used_memory() / (1024 * 1024);
    let ram_percent = if total_ram > 0 {
        (used_ram as f32 / total_ram as f32) * 100.0
    } else {
        0.0
    };

    let stats = SystemStats {
        cpu_usage: (cpu_usage * 10.0).round() / 10.0,
        ram_used_mb: used_ram,
        ram_total_mb: total_ram,
        ram_percent: (ram_percent * 10.0).round() / 10.0,
    };
    sampler.last = Some((std::time::Instant::now(), stats.clone()));
    Ok(stats)
}

#[tauri::command]
fn get_current_wallpaper() -> Result<String, String> { let _trace = diagnostics::command("get_current_wallpaper"); wallpaper::current_wallpaper() }
#[tauri::command]
async fn set_wallpaper(app: AppHandle, path: String) -> Result<bool, String> {
    let library = app.state::<wallpaper::WallpaperState>().0.clone();
    tauri::async_runtime::spawn_blocking(move || wallpaper::apply_manual(&app, &library, &path)).await.map_err(|e| e.to_string())?
}

pub fn monitor_area(monitor: &tauri::Monitor) -> geometry::Rect {
    let area = monitor.work_area();
    geometry::Rect { x: area.position.x, y: area.position.y, width: area.size.width, height: area.size.height }
}

#[tauri::command]
fn show_dock_context_menu(app: AppHandle, source_dock: Option<String>, icon_center_x: i32, menu_data: serde_json::Value) -> Result<bool, String> {
    let is_list = menu_data["mode"] == "windows";
    let is_audio = menu_data["mode"] == "audio";
    let count = menu_data["windows"].as_array().map_or(0, |v| v.len());
    let (width, height) = if menu_data["mode"] == "system" { (380, 620) } else if is_audio { (360, 540) } else if is_list { (340, 64 + count.min(5) as u32 * 54) }
        else { (340, if menu_data["isRunning"] == true { 550 } else { 370 }) };
    popup::show(&app, "dock-context-menu", icon_center_x, width, height, Some(menu_data), source_dock.as_deref())
}
#[tauri::command]
fn hide_dock_context_menu(app: AppHandle, generation: Option<u64>) -> Result<bool, String> {
    popup::hide(&app, "dock-context-menu", generation)
}
#[tauri::command]
fn is_context_popup_active(app: AppHandle, generation: u64) -> bool {
    popup::active_generation(&app, "dock-context-menu") == Some(generation)
}
#[tauri::command]
fn toggle_calendar_flyout(app: AppHandle, source_dock: Option<String>, anchor_x: i32, anchor_y: i32) -> Result<bool, String> {
    let _ = anchor_y;
    if popup::is_active(&app, "calendar-flyout") && popup::is_for_dock(&app, source_dock.as_deref().unwrap_or("taskbar")) { return popup::hide(&app, "calendar-flyout", None); }
    popup::show(&app, "calendar-flyout", anchor_x, 320, 340, None, source_dock.as_deref())
}
#[tauri::command]
fn hide_calendar_flyout(app: AppHandle) -> Result<bool, String> {
    popup::hide(&app, "calendar-flyout", None)
}

#[tauri::command]
fn is_autostart_enabled() -> bool {
    registration::autostart_file().is_ok_and(|p| p.is_file())
}
#[tauri::command]
fn set_autostart(enabled: bool) -> Result<bool, String> {
    let path = registration::autostart_file()?;
    if enabled { registration::install(&path, true)?; }
    else {
        match fs::remove_file(path) {
            Ok(()) => (),
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => (),
            Err(e) => return Err(e.to_string()),
        }
    }
    Ok(enabled)
}
#[tauri::command]
fn install_app_icon() -> Result<bool, String> {
    registration::install(&registration::application_file()?, false)?;
    Ok(true)
}

#[tauri::command]
fn get_open_windows(state: tauri::State<window_manager::WindowSnapshots>) -> Result<Vec<OpenWindow>, WindowError> { let _trace = diagnostics::command("get_open_windows"); state.get() }
#[tauri::command]
fn activate_window(window_id: WindowId, state: tauri::State<window_manager::WindowSnapshots>) -> Result<bool, WindowError> {
    let result = window_manager::backend()?.activate(&window_id);
    state.invalidate();
    result
}
#[tauri::command]
fn close_window(xid: WindowId, state: tauri::State<window_manager::WindowSnapshots>) -> Result<bool, WindowError> {
    let result = window_manager::backend()?.close(&xid);
    state.invalidate();
    result
}
#[tauri::command]
fn force_kill_window(xid: WindowId, state: tauri::State<window_manager::WindowSnapshots>) -> Result<bool, WindowError> {
    let result = window_manager::backend()?.force_kill(&xid);
    state.invalidate();
    result
}

#[tauri::command]
fn spawn_app(exec_cmd: String) -> Result<bool, String> {
    let cmd = exec_cmd.trim();
    if cmd.is_empty() {
        return Err("app_command_empty: Lệnh mở ứng dụng không được để trống".to_string());
    }

    if let Some(id) = cmd.strip_prefix("desktop:") {
        return applications::launch_installed_app(id.into(), None);
    }
    let argv = gio::glib::shell_parse_argv(cmd).map_err(|e| format!("app_command_invalid: {e}"))?;
    let executable = argv.first().ok_or("app_command_empty")?;
    let mut child = Command::new(executable).args(&argv[1..]).spawn().map_err(|e| format!("app_launch_failed: {e}"))?;
    std::thread::spawn(move || { let _ = child.wait(); });
    Ok(true)
}

#[tauri::command]
fn launch_app(command: String) -> Result<bool, String> {
    spawn_app(command)
}

#[tauri::command]
fn show_app_launcher(app: AppHandle, icon_center_x: Option<i32>, source_dock: Option<String>) -> Result<bool, String> {
    let anchor = match icon_center_x {
        Some(anchor) => anchor,
        None => {
            let dock = layout::dock(&app, source_dock.as_deref())?;
            (f64::from(dock.outer_size().map_err(|e| e.to_string())?.width) / dock.scale_factor().map_err(|e| e.to_string())? / 2.).round() as i32
        }
    };
    popup::show(&app, "dock-context-menu", anchor, 500, 580, Some(serde_json::json!({"mode":"launcher","appName":"Ứng dụng"})), source_dock.as_deref())
}

#[tauri::command]
fn get_calendar_visibility(app: AppHandle) -> bool { popup::is_active(&app, "calendar-flyout") }

#[tauri::command]
fn show_studio(app: AppHandle) -> Result<(), String> {
    let window = app.get_webview_window("main").ok_or("Không tìm thấy Studio")?;
    window.show().and_then(|_| window.unminimize()).and_then(|_| window.set_focus()).map_err(|e| e.to_string())
}
#[derive(Default)]
struct LauncherStartup(Mutex<(bool, Option<instance::Request>)>);
fn dispatch_request(app: AppHandle, request: instance::Request) -> Result<(), String> {
    match request {
        instance::Request::Studio => {
            app.state::<LauncherStartup>().0.lock().map_err(|_| "launcher_startup_lock")?.1 = None;
            show_studio(app)
        }
        instance::Request::Launcher { activation_token } => {
            let config_ready = app.state::<config::ConfigState>().0.lock().map_err(|_| "config_lock")?.initialized;
            let state = app.state::<LauncherStartup>();
            let mut startup = state.0.lock().map_err(|_| "launcher_startup_lock")?;
            if !startup.0 || !config_ready {
                startup.1 = Some(instance::Request::Launcher { activation_token });
                return Ok(());
            }
            drop(startup);
            popup::show_unanchored_launcher(&app, activation_token.as_deref()).map(|_| ())
        }
    }
}
#[tauri::command]
fn launcher_surface_ready(app: AppHandle, window: tauri::WebviewWindow) -> Result<(), String> {
    if window.label() != "dock-context-menu" { return Err("launcher_surface_invalid".into()); }
    {
        let state = app.state::<LauncherStartup>();
        let mut startup = state.0.lock().map_err(|_| "launcher_startup_lock")?;
        startup.0 = true;
    }
    flush_launcher_startup(&app);
    Ok(())
}
fn flush_launcher_startup(app: &AppHandle) {
    let handle = app.clone();
    // Defer within the GTK loop until config publish has mapped the Dock. No
    // delayed activation timer may steal focus from a newer user choice.
    gio::glib::idle_add_local_once(move || {
        let pending = {
            let state = handle.state::<LauncherStartup>();
            let mut startup = match state.0.lock() { Ok(value) => value, Err(_) => return };
            if startup.0 { startup.1.take() } else { None }
        };
        if let Some(request) = pending {
            if let Err(error) = dispatch_request(handle, request) { eprintln!("launcher_startup: {error}"); }
        }
    });
}
#[tauri::command]
fn focus_dock(app: AppHandle) -> Result<(), String> {
    use gtk::prelude::*;
    let state = app.state::<config::ConfigState>();
    if state.0.lock().map_err(|e| e.to_string())?.snapshot.config["enabled"] != true {
        return Err("Dock đang tắt".into());
    }
    let window = app.get_webview_window("taskbar").ok_or("Không tìm thấy Dock")?;
    if !window.is_visible().map_err(|e| e.to_string())? { return Err("Dock đang tắt".into()); }
    window.set_focus().map_err(|e| e.to_string())?;
    window.gtk_window().map_err(|e| e.to_string())?.present();
    window.with_webview(move |platform| {
        // Prepare content focus in the opening gesture. GTK activation settles
        // later; there is no deferred toplevel activation to steal newer focus.
        platform.inner().grab_focus();
    }).map_err(|e| e.to_string())?;
    window.eval("document.querySelector('.taskbar-container button:not(:disabled)')?.focus()").map_err(|e| e.to_string())
}
#[tauri::command]
fn quit_app(app: AppHandle) { app.exit(0); }

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    if let Err(error) = run_app() {
        eprintln!("deskmorph_startup_failed: {error}");
        std::process::exit(1);
    }
}

fn run_app() -> Result<(), String> {
    let args: Vec<_> = std::env::args().skip(1).collect();
    if args == ["--help"] || args == ["-h"] {
        println!("Usage: deskmorph [--launcher]\n\nOpen Studio, or open the application launcher with --launcher.\nRequests target the running instance of the same profile.\nOn Wayland, the compositor decides placement and activation.");
        return Ok(());
    }
    let request = instance::Request::from_args(args)?;
    catalogue_paths::prepare()?;
    let key = registration::config_root()?.join("com.ducthanhdev.deskmorph").to_string_lossy().into_owned();
    let instance = match instance::InstanceGuard::acquire(&key, &request)? {
        Some(instance) => instance,
        None => return Ok(()),
    };
    let mut sys = System::new_all();
    sys.refresh_all();

    tauri::Builder::default()
        .manage(LauncherStartup(Mutex::new((false, if request == instance::Request::Studio { None } else { Some(request.clone()) }))))
        .manage(window_manager::WindowSnapshots::default())
        .manage(shortcuts::ShortcutState::default())
        .manage(system_widgets::SystemStatusState::default())
        .manage(media::MediaState::default())
        .manage(audio::AudioState::default())
        .manage(displays::DisplayState::default())
        .manage(wallpaper::WallpaperState::default())
        .manage(tooltip::TooltipState::default())
        .manage(layout::LayoutState::default())
        .manage(applications::AppCatalogue::default())
        .manage(popup::PopupState::default())
        .manage(AppState {
            sys: Mutex::new(SystemSampler { sys, last: None }),
        })
        .setup(move |app| {
            // Mapping the Dock is background UI. Keyboard entry uses an
            // explicit focus_dock/shortcut request instead.
            use gtk::prelude::*;
            app.get_webview_window("taskbar").ok_or("instance_window_missing")?.gtk_window()?.set_focus_on_map(false);
            if request != instance::Request::Studio {
                app.get_webview_window("main").ok_or("instance_window_missing")?.hide()?;
            }
            shortcuts::start(app.handle());
            popup::install_keyboard(app.handle()).map_err(std::io::Error::other)?;
            tooltip::install(app.handle()).map_err(std::io::Error::other)?;
            app.manage(instance.start(app.handle().clone()).map_err(std::io::Error::other)?);
            applications::watch(app.handle());
            layout::watch(app.handle());
            let path = registration::config_root().map_err(std::io::Error::other)?.join("com.ducthanhdev.deskmorph/config.json");
            let store = config::ConfigStore::load(path)
                .map_err(|e| std::io::Error::other(serde_json::to_string(&e).unwrap_or_default()))?;
            if store.initialized {
                config::publish(app.handle(), &store.snapshot, None)
                    .map_err(|e| std::io::Error::other(serde_json::to_string(&e).unwrap_or_default()))?;
            }
            app.manage(config::ConfigState(Mutex::new(store)));
            wallpaper::start_scheduler(app.handle());
            audio::start(app.handle());
            media::start(app.handle());
            displays::start(app.handle());
            Ok(())
        })
        .on_window_event(|window, event| {
            if layout::is_dock(window.label()) {
                if let tauri::WindowEvent::Resized(size) = event {
                    if let Err(error) = layout::settle_size(window.app_handle(), window.label(), size) { eprintln!("dock_geometry_settle: {error}"); }
                }
            }
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                if window.label() == "main" {
                    let keep = window.app_handle().state::<config::ConfigState>().0.lock()
                        .map(|store| store.snapshot.config["keepDockOnClose"] == true && store.snapshot.config["enabled"] == true).unwrap_or(false);
                    if keep { api.prevent_close(); let _ = window.hide(); }
                    else { window.app_handle().exit(0); }
                } else { api.prevent_close(); let _ = popup::hide(window.app_handle(), window.label(), None); }
            }
            if let tauri::WindowEvent::Focused(false) = event {
                if popup::dismiss_on_blur(window.app_handle(), window.label()) && !window.is_focused().unwrap_or(false) {
                    if let Some(generation) = popup::active_generation(window.app_handle(), window.label()) {
                        let window = window.clone();
                        std::thread::spawn(move || {
                            // Focus notifications from the previous hide/show may arrive late.
                            std::thread::sleep(std::time::Duration::from_millis(120));
                            let check = window.clone();
                            let _ = window.run_on_main_thread(move || {
                                if popup::dismiss_on_blur(check.app_handle(), check.label()) && !check.is_focused().unwrap_or(false) {
                                    let _ = popup::hide(check.app_handle(), check.label(), Some(generation));
                                }
                            });
                        });
                    }
                }
            }
        })
        .invoke_handler(tauri::generate_handler![
            shortcuts::get_launcher_shortcut_status,
            shortcuts::retry_launcher_shortcut,
            layout::is_pointer_over_dock,
            system_widgets::get_system_status,
            system_widgets::open_system_location,
            media::get_media_players,
            media::get_media_artwork,
            media::control_media,
            audio::get_audio_snapshot,
            audio::change_audio,
            wallpaper::get_wallpaper_schedule_status,
            wallpaper::scan_wallpapers,
            wallpaper::cancel_wallpaper_scan,
            wallpaper::wallpaper_thumbnails,
            applications::get_installed_apps,
            applications::launch_installed_app,
            accessibility::announce_accessibility,
            show_app_launcher,
            launcher_surface_ready,
            show_studio,
            focus_dock,
            quit_app,
            displays::get_display_state,
            displays::set_primary_monitor,
            displays::open_display_settings,
            platform::get_platform_info,
            platform::refresh_platform_info,
            config::get_config,
            config::patch_config,
            config::retry_config_apply,
            config::mutate_pin,
            config::review_config_document,
            config::replace_config_document,
            config::export_config,
            get_system_stats,
            wallpaper::shuffle_wallpaper,
            get_current_wallpaper,
            set_wallpaper,
            is_autostart_enabled,
            set_autostart,
            install_app_icon,
            get_open_windows,
            activate_window,
            close_window,
            force_kill_window,
            spawn_app,
            launch_app,
            layout::set_taskbar_autohide_state,
            layout::set_dock_content_width,
            tooltip::set_dock_tooltip,
            show_dock_context_menu,
            hide_dock_context_menu,
            is_context_popup_active,
            toggle_calendar_flyout,
            hide_calendar_flyout,
            get_calendar_visibility
        ])
        .build(tauri::generate_context!())
        .map_err(|error| format!("tauri_initialization: {error}"))?
        .run(|app, event| {
            if matches!(event, tauri::RunEvent::Exit) {
                if let Some(instance) = app.try_state::<instance::InstanceGuard>() { instance.stop(); }
                shortcuts::stop(app);
                applications::stop_watching();
                layout::stop_watching();
                wallpaper::stop_scheduler(app);
                audio::stop(app);
                media::stop(app);
                displays::stop(app);
            }
        });
    Ok(())
}
