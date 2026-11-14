use std::net::TcpStream;
use std::path::PathBuf;
use std::process::{Child, Command};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;
use std::time::{Duration, Instant};
use tauri::menu::{Menu, MenuItem};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::{Manager, WindowEvent};

#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;

const CREATE_NO_WINDOW: u32 = 0x08000000;

struct BackendProcess(Mutex<Option<Child>>);

struct DesktopBehaviorState {
    minimize_to_tray: AtomicBool,
    launch_on_startup: AtomicBool,
}

impl Default for DesktopBehaviorState {
    fn default() -> Self {
        Self {
            minimize_to_tray: AtomicBool::new(true),
            launch_on_startup: AtomicBool::new(false),
        }
    }
}

impl Drop for BackendProcess {
    fn drop(&mut self) {
        if let Ok(mut lock) = self.0.lock() {
            if let Some(mut child) = lock.take() {
                let _ = child.kill();
            }
        }
    }
}

fn terminate_backend(app_handle: &tauri::AppHandle) {
    if let Some(state) = app_handle.try_state::<BackendProcess>() {
        if let Ok(mut lock) = state.0.lock() {
            if let Some(mut child) = lock.take() {
                let _ = child.kill();
                log::info!("FileNest backend process terminated cleanly.");
            }
        }
    }
}

#[cfg(target_os = "windows")]
fn set_windows_startup_registry(enable: bool) -> Result<(), String> {
    let run_key = r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run";
    let mut cmd = Command::new("reg");
    cmd.creation_flags(CREATE_NO_WINDOW);
    if enable {
        let exe = std::env::current_exe().map_err(|e| format!("Failed to locate executable: {}", e))?;
        let exe_value = format!("\"{}\"", exe.to_string_lossy());
        let status = cmd
            .args(["add", run_key, "/v", "FileNest", "/t", "REG_SZ", "/d", &exe_value, "/f"])
            .status()
            .map_err(|e| format!("Failed to run reg.exe: {}", e))?;
        if !status.success() {
            return Err("Failed to register FileNest Windows startup entry".to_string());
        }
    } else {
        let _ = cmd
            .args(["delete", run_key, "/v", "FileNest", "/f"])
            .status();
    }
    Ok(())
}

#[cfg(not(target_os = "windows"))]
fn set_windows_startup_registry(_enable: bool) -> Result<(), String> {
    Ok(())
}

#[tauri::command]
fn sync_desktop_behavior(
    state: tauri::State<'_, DesktopBehaviorState>,
    launch_on_startup: bool,
    minimize_to_tray: bool,
) -> Result<serde_json::Value, String> {
    state.minimize_to_tray.store(minimize_to_tray, Ordering::Relaxed);
    state.launch_on_startup.store(launch_on_startup, Ordering::Relaxed);
    set_windows_startup_registry(launch_on_startup)?;
    Ok(serde_json::json!({
        "launch_on_startup": launch_on_startup,
        "minimize_to_tray": minimize_to_tray,
    }))
}

#[tauri::command]
fn get_desktop_behavior(state: tauri::State<'_, DesktopBehaviorState>) -> serde_json::Value {
    serde_json::json!({
        "launch_on_startup": state.launch_on_startup.load(Ordering::Relaxed),
        "minimize_to_tray": state.minimize_to_tray.load(Ordering::Relaxed),
    })
}

fn is_port_open(port: u16) -> bool {
    TcpStream::connect(("127.0.0.1", port)).is_ok()
}

fn find_backend_executable(app_handle: &tauri::AppHandle) -> Option<PathBuf> {
    // 1. Check in Tauri resource directory: resources/backend/filenest-backend.exe
    if let Ok(resource_dir) = app_handle.path().resource_dir() {
        let candidate1 = resource_dir.join("resources").join("backend").join("filenest-backend.exe");
        if candidate1.exists() {
            return Some(candidate1);
        }
        let candidate2 = resource_dir.join("backend").join("filenest-backend.exe");
        if candidate2.exists() {
            return Some(candidate2);
        }
        let candidate3 = resource_dir.join("filenest-backend.exe");
        if candidate3.exists() {
            return Some(candidate3);
        }
    }

    // 2. Check next to the running executable
    if let Ok(exe_path) = std::env::current_exe() {
        if let Some(exe_dir) = exe_path.parent() {
            let candidate4 = exe_dir.join("resources").join("backend").join("filenest-backend.exe");
            if candidate4.exists() {
                return Some(candidate4);
            }
            let candidate5 = exe_dir.join("backend").join("filenest-backend.exe");
            if candidate5.exists() {
                return Some(candidate5);
            }
            let candidate6 = exe_dir.join("filenest-backend.exe");
            if candidate6.exists() {
                return Some(candidate6);
            }
        }
    }

    // 3. Check development / workspace paths
    let candidate7 = PathBuf::from("src-tauri/resources/backend/filenest-backend.exe");
    if candidate7.exists() {
        return Some(candidate7);
    }

    None
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![
            sync_desktop_behavior,
            get_desktop_behavior
        ])
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }

            app.manage(BackendProcess(Mutex::new(None)));
            app.manage(DesktopBehaviorState::default());
            let handle = app.handle().clone();

            // Register native Windows System Tray icon & menu
            let open_item = MenuItem::with_id(app, "open", "Open FileNest", true, None::<&str>)?;
            let hide_item = MenuItem::with_id(app, "hide", "Hide to Tray", true, None::<&str>)?;
            let quit_item = MenuItem::with_id(app, "quit", "Exit", true, None::<&str>)?;
            let tray_menu = Menu::with_items(app, &[&open_item, &hide_item, &quit_item])?;

            let mut tray_builder = TrayIconBuilder::with_id("filenest-tray")
                .tooltip("FileNest Desktop & Storage Manager")
                .menu(&tray_menu)
                .show_menu_on_left_click(false)
                .on_menu_event(|app_handle, event| match event.id.as_ref() {
                    "open" => {
                        if let Some(window) = app_handle.get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.unminimize();
                            let _ = window.set_focus();
                        }
                    }
                    "hide" => {
                        if let Some(window) = app_handle.get_webview_window("main") {
                            let _ = window.hide();
                        }
                    }
                    "quit" => {
                        terminate_backend(app_handle);
                        app_handle.exit(0);
                    }
                    _ => {}
                })
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        ..
                    } = event
                    {
                        if let Some(window) = tray.app_handle().get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.unminimize();
                            let _ = window.set_focus();
                        }
                    }
                });

            if let Some(icon) = app.default_window_icon() {
                tray_builder = tray_builder.icon(icon.clone());
            }
            tray_builder.build(app)?;

            // Automatically supervise and launch backend if not already running on port 8000
            if !is_port_open(8000) {
                if let Some(backend_exe) = find_backend_executable(&handle) {
                    log::info!("FileNest backend binary located at: {:?}", backend_exe);
                    let mut cmd = Command::new(&backend_exe);
                    #[cfg(target_os = "windows")]
                    cmd.creation_flags(CREATE_NO_WINDOW);

                    match cmd.spawn() {
                        Ok(child) => {
                            if let Some(state) = app.try_state::<BackendProcess>() {
                                if let Ok(mut lock) = state.0.lock() {
                                    *lock = Some(child);
                                }
                            }

                            // Wait up to 15 seconds for local backend health
                            let start = Instant::now();
                            while start.elapsed() < Duration::from_secs(15) {
                                if is_port_open(8000) {
                                    log::info!("FileNest backend successfully started and listening on port 8000.");
                                    break;
                                }
                                std::thread::sleep(Duration::from_millis(200));
                            }
                        }
                        Err(e) => {
                            log::error!("Failed to launch FileNest backend process: {}", e);
                        }
                    }
                } else {
                    log::warn!("FileNest standalone backend executable not found. Expecting external or dev server on port 8000.");
                }
            } else {
                log::info!("Backend service already active on port 8000.");
            }

            Ok(())
        })
        .on_window_event(|window, event| match event {
            WindowEvent::CloseRequested { api, .. } => {
                let minimize = window
                    .try_state::<DesktopBehaviorState>()
                    .map(|s| s.minimize_to_tray.load(Ordering::Relaxed))
                    .unwrap_or(false);
                if minimize {
                    api.prevent_close();
                    let _ = window.hide();
                } else {
                    terminate_backend(window.app_handle());
                }
            }
            WindowEvent::Destroyed => {
                terminate_backend(window.app_handle());
            }
            _ => {}
        })
        .run(tauri::generate_context!())
        .expect("error while building tauri application");
}
