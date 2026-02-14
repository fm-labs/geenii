mod docker;

use serde::{Deserialize, Serialize};
//use tauri::image::Image;
//use tauri::menu::Menu;
use tauri::path::BaseDirectory;
//use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use std::sync::{
    atomic::{AtomicBool, Ordering},
    Mutex,
};
use tauri::{App, AppHandle, Manager, RunEvent, State};
use tauri_plugin_shell::{process::CommandChild, process::CommandEvent, ShellExt};

pub struct ServerState {
    pub child: Mutex<Option<CommandChild>>,
    pub started: AtomicBool,
}

// impl Drop for ServerState {
//     fn drop(&mut self) {
//         if let Some(child) = self.child.lock().unwrap().take() {
//             let _ = child.kill();
//         }
//     }
// }

#[derive(Debug, Serialize, Deserialize)]
struct CommandResult {
    success: bool,
    stdout: String,
    stderr: String,
    exit_code: Option<i32>,
}

// Learn more about Tauri commands at https://tauri.app/develop/calling-rust/
#[tauri::command]
fn greet(name: &str) -> String {
    format!("HelloScreen, {}! You've been greeted from Rust!", name)
}

#[tauri::command]
fn prompt(prompt: &str) -> String {
    format!("Your wish is my command! You requested: {}", prompt)
}

// Basic command execution
#[tauri::command]
async fn execute_command(
    app: AppHandle,
    command: String,
    args: Vec<String>,
) -> Result<CommandResult, String> {
    let shell = app.shell();

    let output = shell
        .command(command)
        .args(args)
        .output()
        .await
        .map_err(|e| format!("Failed to execute command: {}", e))?;

    Ok(CommandResult {
        success: output.status.success(),
        stdout: String::from_utf8_lossy(&output.stdout).to_string(),
        stderr: String::from_utf8_lossy(&output.stderr).to_string(),
        exit_code: output.status.code(),
    })
}

// Spawn built-in python server sidecar
// #[tauri::command]
// async fn start_python_sidecar(app: &tauri::AppHandle) -> Result<(), String> {
//     let sidecar_cmd = app
//         .shell()
//         .sidecar("binaries/geenii-srv")
//         .map_err(|e| e.to_string())?;
//
//     // no args in this example; you could pass e.g. ["--port", "8765"]
//     let (_rx, _child) = sidecar_cmd.spawn().map_err(|e| e.to_string())?;
//
//     // For a long-running FastAPI server, the process will just stay alive.
//     // If you want to stop it later, store `_child` somewhere in app state.
//     Ok(())
// }

#[cfg(desktop)]
pub fn check_all_tauri_paths(app_handle: &AppHandle) -> Vec<bool> {
    let directories = vec![
        ("Audio", BaseDirectory::Audio),
        ("Cache", BaseDirectory::Cache),
        ("Config", BaseDirectory::Config),
        ("Data", BaseDirectory::Data),
        ("LocalData", BaseDirectory::LocalData),
        ("Document", BaseDirectory::Document),
        ("Download", BaseDirectory::Download),
        ("Picture", BaseDirectory::Picture),
        ("Public", BaseDirectory::Public),
        ("Video", BaseDirectory::Video),
        ("Resource", BaseDirectory::Resource),
        ("Temp", BaseDirectory::Temp),
        ("AppConfig", BaseDirectory::AppConfig),
        ("AppData", BaseDirectory::AppData),
        ("AppLocalData", BaseDirectory::AppLocalData),
        ("AppCache", BaseDirectory::AppCache),
        ("AppLog", BaseDirectory::AppLog),
        ("Desktop", BaseDirectory::Desktop),
        ("Executable", BaseDirectory::Executable),
        ("Font", BaseDirectory::Font),
        ("Home", BaseDirectory::Home),
        ("Runtime", BaseDirectory::Runtime),
        ("Template", BaseDirectory::Template),
    ];

    directories
        .into_iter()
        .map(|(name, dir)| {
            //let mut check = check_path_accessibility(app_handle, dir);
            //println!("Checking path: {} -> {}", name, check);
            println!("Checking base dir: {}", name);

            let mut check = false;
            match app_handle.path().resolve("", dir) {
                Ok(path) => {
                    let _path = Some(path.to_string_lossy().to_string());
                    check = path.exists();
                    println!("Base directory {} ({:?}) exists: {}", name, _path, check);
                }
                Err(e) => {
                    println!("Error resolving path for {}: {}", name, e);
                }
            }
            check
        })
        .collect()
}

#[cfg(desktop)]
pub fn setup_path_checker(app: &mut App) -> Result<(), Box<dyn std::error::Error>> {
    let app_handle = app.handle().clone();

    // Run the check on startup
    tauri::async_runtime::spawn(async move {
        let _checks = check_all_tauri_paths(&app_handle);
        //print_path_report(&checks);
    });

    Ok(())
}

#[cfg(desktop)]
pub fn setup_autostart(app: &mut App) -> Result<(), Box<dyn std::error::Error>> {
    {
        use tauri_plugin_autostart::MacosLauncher;
        use tauri_plugin_autostart::ManagerExt;

        app.handle()
            .plugin(tauri_plugin_autostart::init(
                MacosLauncher::LaunchAgent,
                Some(vec![]),
            ))
            .expect("Failed to setup plugin");

        // Get the autostart manager
        let autostart_manager = app.autolaunch();
        // Enable autostart
        let _ = autostart_manager.enable();
        // Check enable state
        println!(
            "registered for autostart? {}",
            autostart_manager.is_enabled().unwrap()
        );
        // Disable autostart
        //let _ = autostart_manager.disable();
    }
    Ok(())
}

async fn start_server_internal(app: AppHandle) -> Result<(), String> {
    let state = app.state::<ServerState>();

    // prevent double-start (atomic, cross-thread safe)
    if state.started.swap(true, Ordering::SeqCst) {
        return Ok(());
    }

    let mut guard = state.child.lock().unwrap();
    if guard.is_some() {
        return Ok(());
    }

    let (mut rx, child) = app
        .shell()
        .sidecar("geenii-srv")
        .map_err(|e| e.to_string())?
        //.args(["8787"])
        .spawn()
        .map_err(|e| e.to_string())?;

    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            println!("sidecar: {:?}", event);
            match event {
                CommandEvent::Stdout(bytes) => {
                    print!("{}", String::from_utf8_lossy(&bytes));
                }
                CommandEvent::Stderr(bytes) => {
                    eprint!("{}", String::from_utf8_lossy(&bytes));
                }
                CommandEvent::Error(err) => {
                    eprintln!("sidecar error: {err}");
                }
                CommandEvent::Terminated(p) => {
                    eprintln!(
                        "sidecar terminated: code={:?} signal={:?}",
                        p.code, p.signal
                    );
                }
                _ => {}
            }
        }
    });

    *guard = Some(child);
    Ok(())
}

#[tauri::command]
async fn start_server(app: AppHandle) -> Result<(), String> {
    start_server_internal(app).await
}

#[cfg(desktop)]
pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_process::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        //.plugin(tauri_plugin_autostart::init())
        // .setup(|app| {
        //     setup_path_checker(app)?;
        //
        //     //let quit_i = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
        //     //let menu = Menu::with_items(app, &[&quit_i])?;
        //
        //     let empty_menu = Menu::new(app)?;
        //
        //     //let tray_icon = Image::from_bytes(include_bytes!("../icons/icon.icns"));
        //     let tray_icon = Image::from_path("icons/32x32.png").expect("Failed to load tray icon");
        //     let _tray = TrayIconBuilder::new()
        //         .icon(tray_icon)
        //         .tooltip("Ask geenii")
        //         .menu(&empty_menu)
        //         .on_menu_event(|app, event| match event.id.as_ref() {
        //             "quit" => {
        //                 println!("quit menu item was clicked");
        //                 app.exit(0);
        //             }
        //             _ => {
        //                 println!("menu item {:?} not handled", event.id);
        //             }
        //         })
        //         .on_tray_icon_event(|tray, event| match event {
        //             TrayIconEvent::Click {
        //                 button: MouseButton::Left,
        //                 button_state: MouseButtonState::Up,
        //                 ..
        //             } => {
        //                 //println!("left click pressed and released");
        //                 let app = tray.app_handle();
        //                 if let Some(window) = app.get_webview_window("main") {
        //                     let _ = window.show();
        //                     let _ = window.set_focus();
        //                 }
        //             }
        //             _ => {
        //                 //println!("unhandled event {event:?}");
        //             }
        //         })
        //         .build(app)?;
        //     Ok(())
        // })
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_opener::init())
        .manage(ServerState {
            child: Mutex::new(None),
            started: AtomicBool::new(false),
        })
        .invoke_handler(tauri::generate_handler![
            greet,
            prompt,
            execute_command,
            start_server
        ])
        .setup(|app| {
            let app_handle = app.handle().clone(); // owned, 'static
                                                   // fire and forget: start sidecar when app starts
            tauri::async_runtime::spawn(async move {
                eprintln!("Starting sidecar server...");
                if let Err(e) = start_server_internal(app_handle).await {
                    eprintln!("Failed to start server: {e}");
                }
            });

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while running tauri application");

    app.run(|app_handle, event| {
        match event {
            // Fired when the app is about to quit (Cmd+Q, close last window on some platforms, app.exit(), etc.)
            RunEvent::ExitRequested { .. } => {
                let state = app_handle.state::<ServerState>();
                if let Some(child) = state.child.lock().unwrap().take() {
                    let _ = child.kill();
                    eprintln!("Sidecar killed on ExitRequested");
                };
            }

            // (Optional) extra safety: if you prefer, also handle final exit
            RunEvent::Exit => {
                let state = app_handle.state::<ServerState>();
                if let Some(child) = state.child.lock().unwrap().take() {
                    let _ = child.kill();
                    eprintln!("Sidecar killed on Exit");
                };
            }

            _ => {}
        }
    });
}

// #[cfg_attr(mobile, tauri::mobile_entry_point)]
// pub fn run_mobile() {
//     tauri::Builder::default()
//         .run(tauri::generate_context!())
//         .expect("error while running tauri application");
// }
