use std::process::{Child, Command};
use std::sync::Mutex;
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

    let state = app.state::<ServerProcess>();
    *state.0.lock().unwrap() = Some(child);

    println!("Python server started (pid: {:?})",
             app.state::<ServerProcess>().0.lock().unwrap().as_ref().map(|c| c.pid()));

    Ok(())
}

pub fn stop_server(app: &tauri::AppHandle) {
    let state = app.state::<ServerProcess>();
    let mut lock = state.0.lock().unwrap();
    if let Some(mut child) = lock.take() {
        // print the pid of the process being killed
        println!("Stopping Python server (pid: {:?})", child.pid());

        let _ = child.kill();
        //let _ = child.wait(); // reap zombie process
        println!("Stopping Python server...");

        // Wait a moment to ensure the process has terminated before printing the final message
        std::thread::sleep(std::time::Duration::from_millis(3000));
        println!("Python server stopped");
    }

    // run a system command to kill any remaining processes with the same name (as a fallback)
    #[cfg(target_os = "windows")]
    {
        println!("Killing any remaining server processes with name: {}", crate::server::server_binary_name());
        let _ = Command::new("taskkill")
            .args(["/F", "/IM", server_binary_name()])
            .output();
    }
    #[cfg(not(target_os = "windows"))]
    {
        println!("Killing any remaining server processes with name: {}", server_binary_name());
        let _ = Command::new("pkill")
            .args(["-f", server_binary_name()])
            .output();
    }
}

/// Returns platform-specific binary name
fn server_binary_name() -> &'static str {
    #[cfg(target_os = "windows")]
    return "geenii-srv.exe";
    #[cfg(not(target_os = "windows"))]
    return "geenii-srv";
}