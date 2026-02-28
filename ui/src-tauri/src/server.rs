use std::fs::OpenOptions;
use std::io::Write;
use std::process::{Child, Command};
use std::sync::{Arc, Mutex};
use tauri::Manager;
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

//pub struct ServerProcess(pub Mutex<Option<Child>>);
pub struct ServerProcess(pub Mutex<Option<CommandChild>>);

pub fn start_server(app: &tauri::AppHandle) -> Result<(), String> {
    // Resolve the binary path (bundled with app)
    // let resource_path = app
    //     .path()
    //     .resource_dir()
    //     .map_err(|e| e.to_string())?
    //     .join("binaries")
    //     .join(server_binary_name());
    //
    // let child = Command::new(&resource_path)
    //     .spawn()
    //     .map_err(|e| format!("Failed to start server: {}", e))?;

    // Logging setup
    // TODO: refactor using rust tracing or tauri logger plugin
    let app_dir = app.path().app_log_dir().map_err(|e| e.to_string())?;
    std::fs::create_dir_all(&app_dir)
        .map_err(|e| format!("Failed to create log directory: {}", e))?;

    let log_path = app_dir.join("geeniid.log");
    println!("Log file path: {:?}", log_path);
    let log_file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(&log_path)
        .map_err(|e| e.to_string())?;

    // Wrap in Arc<Mutex<>> so async task can use it safely
    let log_file = Arc::new(Mutex::new(log_file));
    let log_file_clone = log_file.clone();

    // Spawn the sidecar process using the plugin
    let (mut rx, child) = app
        .shell()
        //.sidecar(server_binary_name())
        .sidecar("geeniid")
        .map_err(|e| e.to_string())?
        //.args(["8787"])
        .spawn()
        .map_err(|e| e.to_string())?;

    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(bytes) => {
                    let text = String::from_utf8_lossy(&bytes);
                    print!("{}", text);

                    if let Ok(mut file) = log_file_clone.lock() {
                        let _ = writeln!(file, "{}", text);
                    }
                }
                CommandEvent::Stderr(bytes) => {
                    let text = String::from_utf8_lossy(&bytes);
                    eprint!("{}", text);

                    if let Ok(mut file) = log_file_clone.lock() {
                        let _ = writeln!(file, "ERROR: {}", text);
                    }
                }
                CommandEvent::Error(err) => {
                    eprintln!("sidecar error: {err}");

                    if let Ok(mut file) = log_file_clone.lock() {
                        let _ = writeln!(file, "SIDECAR ERROR: {}", err);
                    }
                }
                CommandEvent::Terminated(p) => {
                    let msg = format!(
                        "sidecar terminated: code={:?} signal={:?}",
                        p.code, p.signal
                    );
                    eprintln!("{}", msg);

                    if let Ok(mut file) = log_file_clone.lock() {
                        let _ = writeln!(file, "{}", msg);
                    }
                }
                _ => {}
            }
        }
    });

    let state = app.state::<ServerProcess>();
    *state.0.lock().unwrap() = Some(child);

    println!(
        "{:?} started (pid: {:?})",
        server_binary_name(),
        app.state::<ServerProcess>()
            .0
            .lock()
            .unwrap()
            .as_ref()
            .map(|c| c.pid())
    );

    Ok(())
}

pub fn stop_server(app: &tauri::AppHandle) {
    let state = app.state::<ServerProcess>();
    let mut lock = state.0.lock().unwrap();
    if let Some(mut child) = lock.take() {
        println!(
            "Stopping {:?} (pid: {:?})",
            server_binary_name(),
            child.pid()
        );

        let _ = child.kill();
        //let _ = child.wait(); // reap zombie process
        //println!("Stopping Python server...");

        // Wait a moment to ensure the process has terminated before printing the final message
        std::thread::sleep(std::time::Duration::from_millis(1300));
        println!("Bye!");
    }

    // run a system command to kill any remaining processes with the same name (as a fallback)
    #[cfg(target_os = "windows")]
    {
        println!(
            "Killing any remaining server processes with name: {}",
            crate::server::server_binary_name()
        );
        let _ = Command::new("taskkill")
            .args(["/F", "/IM", server_binary_name()])
            .output();
    }
    #[cfg(not(target_os = "windows"))]
    {
        println!(
            "Killing any remaining server processes with name: {}",
            server_binary_name()
        );
        let _ = Command::new("pkill")
            .args(["-f", server_binary_name()])
            .output();
    }
}

/// Returns platform-specific binary name
fn server_binary_name() -> &'static str {
    #[cfg(target_os = "windows")]
    return "geeniid.exe";
    #[cfg(not(target_os = "windows"))]
    return "geeniid";
}
