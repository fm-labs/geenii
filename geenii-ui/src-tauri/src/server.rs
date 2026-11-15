//! Background geenii server.
//!
//! On startup the app makes sure a geenii server answers on the pinned port:
//!
//! 0. Stop servers this app started that outlived it (see `stop_orphaned_servers`).
//! 1. If something already answers `/api/v1/health`, use it.
//! 2. Otherwise install the pinned PyInstaller onedir release (see
//!    `server-release.json`) into `$AppCache/server/<version>/`, downloading it
//!    from GitHub once and verifying its SHA-256 against the pinned checksum.
//! 3. Spawn `<install>/geenii/geenii server start ...` and wait until healthy.
//!
//! Progress is published as `server-status` events (and the `server_status`
//! command); `server_restart` retries after a failure.
//!
//! `GEENII_SERVER_BIN=/path/to/geenii` skips the download and runs that binary
//! instead. In dev mode the server is only started when that variable is set.

use std::collections::HashMap;
use std::fs::{File, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex, Once};
use std::time::{Duration, Instant};

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use tauri::{AppHandle, Emitter, Manager};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;
use tokio::io::AsyncWriteExt;

const MANIFEST_JSON: &str = include_str!("../server-release.json");
const BIN_OVERRIDE_ENV: &str = "GEENII_SERVER_BIN";
pub const STATUS_EVENT: &str = "server-status";
const STARTUP_TIMEOUT: Duration = Duration::from_secs(60);
/// How long a stopping server gets to shut down after SIGTERM before it is killed.
const STOP_GRACE: Duration = Duration::from_secs(5);

#[derive(Debug, Deserialize)]
struct ReleaseManifest {
    version: String,
    url: String,
    binary: String,
    args: Vec<String>,
    port: u16,
    sha256: HashMap<String, String>,
}

impl ReleaseManifest {
    fn load() -> Result<Self, String> {
        serde_json::from_str(MANIFEST_JSON).map_err(|e| format!("invalid server-release.json: {e}"))
    }

    fn archive_url(&self, target: &str) -> String {
        self.url
            .replace("{version}", &self.version)
            .replace("{target}", target)
    }

    fn expected_sha256(&self, target: &str) -> Result<String, String> {
        match self.sha256.get(target).map(|s| s.trim().to_lowercase()) {
            Some(s) if s.len() == 64 && s.chars().all(|c| c.is_ascii_hexdigit()) => Ok(s),
            _ => Err(format!(
                "no pinned checksum for server {} on {target}; run scripts/pin_server_release.py",
                self.version
            )),
        }
    }
}

#[derive(Clone, Debug, Default, Serialize)]
#[serde(tag = "state", rename_all = "kebab-case")]
pub enum ServerStatus {
    #[default]
    Idle,
    /// Not managed by the app (dev mode without GEENII_SERVER_BIN).
    Disabled,
    Checking,
    Downloading { downloaded: u64, total: Option<u64> },
    Installing,
    Starting,
    /// `external`: a server was already running and is used as is.
    Ready { external: bool },
    Failed { error: String },
    Stopped,
}

/// A server process this app started.
struct ManagedChild {
    child: CommandChild,
    /// Set by the output task when the process has terminated.
    exited: Arc<AtomicBool>,
}

#[derive(Default)]
pub struct ServerProcess {
    child: Mutex<Option<ManagedChild>>,
    status: Mutex<ServerStatus>,
    busy: AtomicBool,
}

fn set_status(app: &AppHandle, status: ServerStatus) {
    println!("server status: {status:?}");
    *app.state::<ServerProcess>().status.lock().unwrap() = status.clone();
    let _ = app.emit(STATUS_EVENT, status);
}

/// Starts the server on app startup, unless running in dev mode without an override.
pub fn autostart(app: &AppHandle) {
    // if tauri::is_dev() && std::env::var_os(BIN_OVERRIDE_ENV).is_none() {
    //     println!("Dev mode: not starting the server (set {BIN_OVERRIDE_ENV} to start one).");
    //     set_status(app, ServerStatus::Disabled);
    //     return;
    // }
    start_server(app);
}

/// Starts the server in the background. No-op while a start is already in progress.
pub fn start_server(app: &AppHandle) {
    if app.state::<ServerProcess>().busy.swap(true, Ordering::SeqCst) {
        return;
    }
    let app = app.clone();
    tauri::async_runtime::spawn(async move {
        // Run in its own task so a panic is reported instead of leaving `busy` set.
        let task_app = app.clone();
        let result = tauri::async_runtime::spawn(async move { run(&task_app).await })
            .await
            .unwrap_or_else(|e| Err(format!("server startup task crashed: {e}")));
        if let Err(error) = result {
            eprintln!("server startup failed: {error}");
            set_status(&app, ServerStatus::Failed { error });
        }
        app.state::<ServerProcess>().busy.store(false, Ordering::SeqCst);
    });
}

/// Stops the server process this app started (an external server is left alone):
/// SIGTERM so it can shut down cleanly (and stop its own children), then SIGKILL
/// if it is still running after `STOP_GRACE`. Blocks for at most `STOP_GRACE`.
pub fn stop_server(app: &AppHandle) {
    let managed = app.state::<ServerProcess>().child.lock().unwrap().take();
    if let Some(managed) = managed {
        terminate(managed);
        set_status(app, ServerStatus::Stopped);
    }
}

fn terminate(ManagedChild { child, exited }: ManagedChild) {
    let pid = child.pid();
    #[cfg(unix)]
    {
        println!("Stopping server (pid {pid}): SIGTERM");
        // SAFETY: plain kill(2) on the pid of our own child, which has not been
        // reaped yet if `exited` is unset (the shell plugin reaps it and then sets it).
        if !exited.load(Ordering::SeqCst) && unsafe { libc::kill(pid as libc::pid_t, libc::SIGTERM) } == 0 {
            let deadline = Instant::now() + STOP_GRACE;
            while !exited.load(Ordering::SeqCst) && Instant::now() < deadline {
                std::thread::sleep(Duration::from_millis(50));
            }
        }
    }
    if exited.load(Ordering::SeqCst) {
        println!("Server (pid {pid}) exited");
        return;
    }
    println!("Killing server (pid {pid})");
    if let Err(e) = child.kill() {
        eprintln!("failed to kill server: {e}");
    }
}

/// Stops servers this app started that outlived it: `tauri dev` restarts and crashes
/// skip the exit hook, and a leftover would otherwise be reused as an "external" server,
/// possibly an old version, with nobody owning its lifecycle or logs.
///
/// A server is ours if it runs a binary from our install dir (or `GEENII_SERVER_BIN`),
/// and orphaned if its parent is not a running instance of this app (so the server of
/// a second, live app instance is left alone).
#[cfg(unix)]
async fn stop_orphaned_servers(app: &AppHandle) {
    let mut prefixes = Vec::new();
    if let Ok(cache) = app.path().app_cache_dir() {
        prefixes.push(format!("{}/", cache.join("server").display()));
    }
    if let Some(bin) = std::env::var_os(BIN_OVERRIDE_ENV) {
        prefixes.push(format!("{} ", PathBuf::from(bin).display()));
    }
    let Ok(app_exe) = std::env::current_exe() else { return };
    let app_exe = app_exe.display().to_string();

    let output = match tokio::process::Command::new("ps").args(["-axww", "-o", "pid=,ppid=,command="]).output().await {
        Ok(output) if output.status.success() => output,
        Ok(output) => return eprintln!("orphan check: ps failed: {}", output.status),
        Err(e) => return eprintln!("orphan check: ps failed: {e}"),
    };
    let orphans = find_orphans(&String::from_utf8_lossy(&output.stdout), &prefixes, &app_exe);
    if orphans.is_empty() {
        return;
    }
    let _ = tauri::async_runtime::spawn_blocking(move || {
        for pid in orphans {
            stop_pid(pid);
        }
    })
    .await;
}

#[cfg(not(unix))]
async fn stop_orphaned_servers(_app: &AppHandle) {}

/// Parses `ps -o pid=,ppid=,command=` output; returns the pids of our servers whose
/// parent is not a running `app_exe`.
fn find_orphans(ps_output: &str, prefixes: &[String], app_exe: &str) -> Vec<u32> {
    let procs: Vec<(u32, u32, &str)> = ps_output
        .lines()
        .filter_map(|line| {
            let mut parts = line.trim_start().splitn(2, char::is_whitespace);
            let pid = parts.next()?.parse().ok()?;
            let rest = parts.next()?.trim_start();
            let mut parts = rest.splitn(2, char::is_whitespace);
            let ppid = parts.next()?.parse().ok()?;
            Some((pid, ppid, parts.next().unwrap_or("").trim_start()))
        })
        .collect();
    let is_app = |pid: u32| {
        procs.iter().any(|&(p, _, cmd)| p == pid && (cmd == app_exe || cmd.starts_with(&format!("{app_exe} "))))
    };
    procs
        .iter()
        .filter(|&&(_, _, cmd)| prefixes.iter().any(|prefix| format!("{cmd} ").starts_with(prefix.as_str())))
        .filter(|&&(_, ppid, _)| !is_app(ppid))
        .map(|&(pid, _, _)| pid)
        .collect()
}

/// SIGTERM, wait up to STOP_GRACE, then SIGKILL; for a process that is not our child.
#[cfg(unix)]
fn stop_pid(pid: u32) {
    let pid = pid as libc::pid_t;
    // SAFETY: kill(2) with a pid just read from ps; signal 0 only probes for existence.
    let alive = || unsafe { libc::kill(pid, 0) } == 0;
    println!("Stopping orphaned server (pid {pid}): SIGTERM");
    if unsafe { libc::kill(pid, libc::SIGTERM) } != 0 {
        return;
    }
    let deadline = Instant::now() + STOP_GRACE;
    while alive() && Instant::now() < deadline {
        std::thread::sleep(Duration::from_millis(50));
    }
    if alive() {
        println!("Killing orphaned server (pid {pid})");
        unsafe { libc::kill(pid, libc::SIGKILL) };
    } else {
        println!("Orphaned server (pid {pid}) exited");
    }
}

#[tauri::command]
pub fn server_status(app: AppHandle) -> ServerStatus {
    app.state::<ServerProcess>().status.lock().unwrap().clone()
}

/// What the frontend needs to know about the desktop shell and its server.
/// Calling it also serves as the frontend's IPC connection check.
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DesktopInfo {
    app_name: String,
    app_version: String,
    tauri_version: &'static str,
    os: &'static str,
    arch: &'static str,
    server_version: String,
    server_url: String,
    /// Set when `GEENII_SERVER_BIN` replaces the downloaded release.
    server_bin_override: Option<String>,
    server_log: Option<String>,
}

#[tauri::command]
pub fn desktop_info(app: AppHandle) -> Result<DesktopInfo, String> {
    let manifest = ReleaseManifest::load()?;
    let package = app.package_info();
    Ok(DesktopInfo {
        app_name: package.name.clone(),
        app_version: package.version.to_string(),
        tauri_version: tauri::VERSION,
        os: std::env::consts::OS,
        arch: std::env::consts::ARCH,
        server_version: manifest.version,
        server_url: format!("http://localhost:{}", manifest.port),
        server_bin_override: std::env::var(BIN_OVERRIDE_ENV).ok(),
        server_log: log_path(&app).ok().map(|p| p.display().to_string()),
    })
}

fn log_path(app: &AppHandle) -> Result<PathBuf, String> {
    Ok(app.path().app_log_dir().map_err(|e| e.to_string())?.join("server.log"))
}

#[tauri::command]
pub fn server_start(app: AppHandle) {
    start_server(&app);
}

/// Stops the server this app started (SIGTERM, then SIGKILL after STOP_GRACE).
/// A server the app did not start is left running.
#[tauri::command]
pub async fn server_stop(app: AppHandle) {
    let _ = tauri::async_runtime::spawn_blocking(move || stop_server(&app)).await;
}

#[tauri::command]
pub async fn server_restart(app: AppHandle) {
    // stop_server can block for up to STOP_GRACE.
    let stop_app = app.clone();
    let _ = tauri::async_runtime::spawn_blocking(move || stop_server(&stop_app)).await;
    start_server(&app);
}

/// reqwest is built with `rustls-no-provider` (shared with the updater plugin):
/// every Client, even a plain-HTTP one, panics unless a provider is installed.
fn ensure_tls_provider() {
    static TLS_INIT: Once = Once::new();
    TLS_INIT.call_once(|| {
        if rustls::crypto::CryptoProvider::get_default().is_none() {
            let _ = rustls::crypto::ring::default_provider().install_default();
        }
    });
}

async fn run(app: &AppHandle) -> Result<(), String> {
    ensure_tls_provider();
    let manifest = ReleaseManifest::load()?;
    let health_url = format!("http://127.0.0.1:{}/api/v1/health", manifest.port);
    let health_client = reqwest::Client::builder()
        .no_proxy()
        .timeout(Duration::from_secs(1))
        .build()
        .map_err(|e| e.to_string())?;

    set_status(app, ServerStatus::Checking);
    stop_orphaned_servers(app).await;
    if is_healthy(&health_client, &health_url).await {
        println!("A server is already running on port {}; using it.", manifest.port);
        set_status(app, ServerStatus::Ready { external: true });
        return Ok(());
    }

    let bin = match std::env::var_os(BIN_OVERRIDE_ENV) {
        Some(path) => PathBuf::from(path),
        None => ensure_installed(app, &manifest).await?,
    };

    set_status(app, ServerStatus::Starting);
    let (exited, log_path) = spawn(app, &bin, &manifest.args)?;

    let deadline = Instant::now() + STARTUP_TIMEOUT;
    loop {
        if exited.load(Ordering::SeqCst) {
            return Err(format!("server exited during startup; see {}", log_path.display()));
        }
        if is_healthy(&health_client, &health_url).await {
            set_status(app, ServerStatus::Ready { external: false });
            return Ok(());
        }
        if Instant::now() > deadline {
            let stop_app = app.clone();
            let _ = tauri::async_runtime::spawn_blocking(move || stop_server(&stop_app)).await;
            return Err(format!(
                "server not healthy after {}s; see {}",
                STARTUP_TIMEOUT.as_secs(),
                log_path.display()
            ));
        }
        tokio::time::sleep(Duration::from_millis(250)).await;
    }
}

async fn is_healthy(client: &reqwest::Client, url: &str) -> bool {
    matches!(client.get(url).send().await, Ok(r) if r.status().is_success())
}

/// Returns the server binary of the pinned release, installing it first if needed.
async fn ensure_installed(app: &AppHandle, manifest: &ReleaseManifest) -> Result<PathBuf, String> {
    let root = app
        .path()
        .app_cache_dir()
        .map_err(|e| e.to_string())?
        .join("server");
    let bin = root.join(&manifest.version).join(&manifest.binary);
    if bin.is_file() {
        return Ok(bin);
    }

    let target = target_tag()?;
    let expected = manifest.expected_sha256(target)?;
    std::fs::create_dir_all(&root).map_err(|e| format!("create {}: {e}", root.display()))?;

    let archive = root.join(format!("{}.tar.gz.download", manifest.version));
    download(app, &manifest.archive_url(target), &archive, &expected).await?;

    set_status(app, ServerStatus::Installing);
    let (r, v, a) = (root.clone(), manifest.version.clone(), archive.clone());
    tauri::async_runtime::spawn_blocking(move || install_archive(&a, &r, &v))
        .await
        .map_err(|e| e.to_string())??;
    let _ = std::fs::remove_file(&archive);
    prune_other_versions(&root, &manifest.version);

    if !bin.is_file() {
        return Err(format!("{} not found in the server archive", manifest.binary));
    }
    Ok(bin)
}

/// Release asset tag for the platform this app was built for.
fn target_tag() -> Result<&'static str, String> {
    if cfg!(all(target_os = "macos", target_arch = "aarch64")) {
        Ok("darwin-arm64")
    } else if cfg!(all(target_os = "macos", target_arch = "x86_64")) {
        Ok("darwin-amd64")
    } else if cfg!(all(target_os = "linux", target_arch = "aarch64")) {
        Ok("linux-arm64")
    } else if cfg!(all(target_os = "linux", target_arch = "x86_64")) {
        Ok("linux-amd64")
    } else {
        Err(format!(
            "no geenii server build for {}-{}",
            std::env::consts::OS,
            std::env::consts::ARCH
        ))
    }
}

/// Downloads `url` to `dest`, failing (and removing `dest`) unless its SHA-256 is `expected`.
async fn download(app: &AppHandle, url: &str, dest: &Path, expected: &str) -> Result<(), String> {
    println!("Downloading server from {url}");
    let client = reqwest::Client::builder()
        .user_agent(concat!("geenii-desktop/", env!("CARGO_PKG_VERSION")))
        .connect_timeout(Duration::from_secs(15))
        .read_timeout(Duration::from_secs(60))
        .build()
        .map_err(|e| e.to_string())?;
    let mut response = client
        .get(url)
        .send()
        .await
        .and_then(|r| r.error_for_status())
        .map_err(|e| format!("download failed: {e}"))?;

    let total = response.content_length();
    let mut file = tokio::fs::File::create(dest)
        .await
        .map_err(|e| format!("create {}: {e}", dest.display()))?;
    let mut hasher = Sha256::new();
    let mut downloaded = 0u64;
    let mut last_report = 0u64;
    set_status(app, ServerStatus::Downloading { downloaded, total });

    let result: Result<(), String> = async {
        while let Some(chunk) = response
            .chunk()
            .await
            .map_err(|e| format!("download failed: {e}"))?
        {
            hasher.update(&chunk);
            file.write_all(&chunk).await.map_err(|e| e.to_string())?;
            downloaded += chunk.len() as u64;
            if downloaded - last_report >= 512 * 1024 {
                last_report = downloaded;
                set_status(app, ServerStatus::Downloading { downloaded, total });
            }
        }
        file.flush().await.map_err(|e| e.to_string())?;
        let actual = format!("{:x}", hasher.finalize());
        if actual != expected {
            return Err(format!(
                "checksum mismatch for {url}: expected {expected}, got {actual}"
            ));
        }
        Ok(())
    }
    .await;

    drop(file);
    if result.is_err() {
        let _ = std::fs::remove_file(dest);
    }
    result
}

/// Unpacks `archive` into `<root>/<version>`, via a `.partial` directory so an
/// interrupted install never looks complete.
fn install_archive(archive: &Path, root: &Path, version: &str) -> Result<(), String> {
    let partial = root.join(format!("{version}.partial"));
    let dest = root.join(version);
    if partial.exists() {
        std::fs::remove_dir_all(&partial).map_err(|e| format!("remove {}: {e}", partial.display()))?;
    }
    std::fs::create_dir_all(&partial).map_err(|e| e.to_string())?;

    let file = File::open(archive).map_err(|e| format!("open {}: {e}", archive.display()))?;
    let mut tar = tar::Archive::new(flate2::read::GzDecoder::new(file));
    tar.set_preserve_permissions(true);
    // Archive::unpack refuses entries that would land outside `partial`.
    tar.unpack(&partial).map_err(|e| format!("extract server archive: {e}"))?;

    if dest.exists() {
        std::fs::remove_dir_all(&dest).map_err(|e| format!("remove {}: {e}", dest.display()))?;
    }
    std::fs::rename(&partial, &dest).map_err(|e| format!("install {}: {e}", dest.display()))
}

/// Removes installs, partial extractions and downloads of other server versions.
fn prune_other_versions(root: &Path, keep: &str) {
    let Ok(entries) = std::fs::read_dir(root) else { return };
    for entry in entries.flatten() {
        if entry.file_name().to_string_lossy() == keep {
            continue;
        }
        let path = entry.path();
        let result = if path.is_dir() {
            std::fs::remove_dir_all(&path)
        } else {
            std::fs::remove_file(&path)
        };
        match result {
            Ok(()) => println!("Removed old server files {}", path.display()),
            Err(e) => eprintln!("failed to remove {}: {e}", path.display()),
        }
    }
}

/// Spawns the server and forwards its output to the log file.
/// Returns a flag set when the process terminates, and the log path.
fn spawn(app: &AppHandle, bin: &Path, args: &[String]) -> Result<(Arc<AtomicBool>, PathBuf), String> {
    let log_path = log_path(app)?;
    if let Some(log_dir) = log_path.parent() {
        std::fs::create_dir_all(log_dir).map_err(|e| format!("create log directory: {e}"))?;
    }
    let mut log = OpenOptions::new()
        .create(true)
        .append(true)
        .open(&log_path)
        .map_err(|e| e.to_string())?;
    println!("Starting {} {} (log: {})", bin.display(), args.join(" "), log_path.display());

    let mut command = app.shell().command(bin.to_string_lossy().to_string()).args(args);
    // Run in the user's home directory (the server's GEENII_WORKING_DIR defaults to its cwd).
    // PyInstaller locates its bundled files relative to the executable, not the cwd.
    match app.path().home_dir() {
        Ok(home) => command = command.current_dir(home),
        Err(e) => eprintln!("no home directory ({e}); starting server in the current directory"),
    }
    let (mut rx, child) = command
        .spawn()
        .map_err(|e| format!("failed to start {}: {e}", bin.display()))?;
    let pid = child.pid();
    println!("Server started (pid {pid})");
    let exited = Arc::new(AtomicBool::new(false));
    let exited_flag = exited.clone();
    *app.state::<ServerProcess>().child.lock().unwrap() = Some(ManagedChild {
        child,
        exited: exited.clone(),
    });

    let app = app.clone();
    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(bytes) => {
                    let text = String::from_utf8_lossy(&bytes);
                    print!("{text}");
                    let _ = write!(log, "{text}");
                }
                CommandEvent::Stderr(bytes) => {
                    let text = String::from_utf8_lossy(&bytes);
                    eprint!("{text}");
                    let _ = write!(log, "{text}");
                }
                CommandEvent::Error(err) => {
                    eprintln!("server error: {err}");
                    let _ = writeln!(log, "SERVER ERROR: {err}");
                }
                CommandEvent::Terminated(p) => {
                    let msg = format!("server terminated: code={:?} signal={:?}", p.code, p.signal);
                    eprintln!("{msg}");
                    let _ = writeln!(log, "{msg}");
                    exited_flag.store(true, Ordering::SeqCst);
                    // Still registered => not stopped by us: report the crash.
                    // (Compare pids: after a restart the slot holds the new process.)
                    let state = app.state::<ServerProcess>();
                    let crashed = {
                        let mut slot = state.child.lock().unwrap();
                        if slot.as_ref().is_some_and(|m| m.child.pid() == pid) {
                            slot.take();
                            true
                        } else {
                            false
                        }
                    };
                    if crashed {
                        set_status(&app, ServerStatus::Failed { error: msg });
                    }
                }
                _ => {}
            }
        }
    });

    Ok((exited, log_path))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn temp_dir() -> PathBuf {
        let dir = std::env::temp_dir().join(format!("geenii-server-test-{}", uuid::Uuid::new_v4()));
        std::fs::create_dir_all(&dir).unwrap();
        dir
    }

    /// Builds a tar.gz shaped like a release: ./README.md, ./geenii/geenii, ./geenii/_internal/...
    fn make_archive(path: &Path) {
        let file = File::create(path).unwrap();
        let gz = flate2::write::GzEncoder::new(file, flate2::Compression::fast());
        let mut tar = tar::Builder::new(gz);

        let mut add = |name: &str, data: &[u8], mode: u32| {
            let mut header = tar::Header::new_gnu();
            header.set_size(data.len() as u64);
            header.set_mode(mode);
            header.set_cksum();
            tar.append_data(&mut header, name, data).unwrap();
        };
        add("./README.md", b"readme", 0o644);
        add("./geenii/geenii", b"#!/bin/sh\necho ok\n", 0o755);
        add("./geenii/_internal/lib.so.1", b"lib", 0o644);

        let mut link = tar::Header::new_gnu();
        link.set_entry_type(tar::EntryType::Symlink);
        link.set_size(0);
        link.set_mode(0o777);
        link.set_cksum();
        tar.append_link(&mut link, "./geenii/_internal/lib.so", "lib.so.1").unwrap();

        tar.into_inner().unwrap().finish().unwrap();
    }

    /// The JSON shapes the frontend relies on (src/components/tauri/desktop-runtime.ts).
    #[test]
    fn status_serializes_as_frontend_expects() {
        let json = |s: ServerStatus| serde_json::to_value(s).unwrap();
        assert_eq!(json(ServerStatus::Idle), serde_json::json!({"state": "idle"}));
        assert_eq!(
            json(ServerStatus::Downloading { downloaded: 5, total: None }),
            serde_json::json!({"state": "downloading", "downloaded": 5, "total": null})
        );
        assert_eq!(json(ServerStatus::Ready { external: true }), serde_json::json!({"state": "ready", "external": true}));
        assert_eq!(
            json(ServerStatus::Failed { error: "x".into() }),
            serde_json::json!({"state": "failed", "error": "x"})
        );
        let info = serde_json::to_value(DesktopInfo {
            app_name: "a".into(),
            app_version: "1".into(),
            tauri_version: "2",
            os: "macos",
            arch: "aarch64",
            server_version: "v1".into(),
            server_url: "http://localhost:1".into(),
            server_bin_override: None,
            server_log: None,
        })
        .unwrap();
        let mut keys: Vec<_> = info.as_object().unwrap().keys().cloned().collect();
        keys.sort();
        assert_eq!(
            keys,
            ["appName", "appVersion", "arch", "os", "serverBinOverride", "serverLog", "serverUrl", "serverVersion", "tauriVersion"]
        );
    }

    #[test]
    fn find_orphans_matches_only_our_parentless_servers() {
        let app = "/Apps/geenii.app/Contents/MacOS/geenii-desktop";
        let prefixes = vec![
            "/Cache/io.geenii.desktop/server/".to_string(),
            "/dev/dist/geenii ".to_string(),
        ];
        let ps = "\
            1     0 /sbin/launchd
          100     1 /Apps/geenii.app/Contents/MacOS/geenii-desktop
          200     1 /Cache/io.geenii.desktop/server/v1/geenii/geenii server start --port 33311
          201   100 /Cache/io.geenii.desktop/server/v2/geenii/geenii server start --port 33311
          202   999 /dev/dist/geenii server start
          203     1 /dev/dist/geenii-other server start
          204     1 /usr/bin/python3 /Cache/io.geenii.desktop/server/v1/x.py
          205     1 /Cache/other.app/server/v1/geenii/geenii server start
        ";
        // 200: orphaned (parent launchd); 202: parent gone. 201: live app instance.
        // 203/204/205: not our binaries.
        assert_eq!(find_orphans(ps, &prefixes, app), vec![200, 202]);
    }

    #[test]
    fn manifest_parses() {
        let m = ReleaseManifest::load().unwrap();
        assert!(m.version.starts_with('v'));
        assert!(m.archive_url("darwin-arm64").ends_with(&format!(
            "/{0}/geenii-darwin-arm64-{0}.tar.gz",
            m.version
        )));
        for target in ["darwin-amd64", "darwin-arm64", "linux-amd64", "linux-arm64"] {
            assert!(m.sha256.contains_key(target), "missing target {target}");
        }
    }

    #[test]
    fn expected_sha256_rejects_empty_and_malformed() {
        let mut m = ReleaseManifest::load().unwrap();
        m.sha256.insert("x".into(), "".into());
        m.sha256.insert("y".into(), "abc".into());
        m.sha256.insert("z".into(), "AB".repeat(32));
        assert!(m.expected_sha256("x").is_err());
        assert!(m.expected_sha256("y").is_err());
        assert!(m.expected_sha256("missing").is_err());
        assert_eq!(m.expected_sha256("z").unwrap(), "ab".repeat(32));
    }

    #[test]
    fn install_archive_unpacks_atomically_and_keeps_modes_and_links() {
        let root = temp_dir();
        let archive = root.join("v1.tar.gz.download");
        make_archive(&archive);
        // Leftover from an interrupted install must not break the next one.
        std::fs::create_dir_all(root.join("v1.partial/junk")).unwrap();

        install_archive(&archive, &root, "v1").unwrap();

        let bin = root.join("v1/geenii/geenii");
        assert!(bin.is_file());
        assert!(!root.join("v1.partial").exists());
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            assert_eq!(std::fs::metadata(&bin).unwrap().permissions().mode() & 0o777, 0o755);
            let link = root.join("v1/geenii/_internal/lib.so");
            assert!(std::fs::symlink_metadata(&link).unwrap().file_type().is_symlink());
            assert_eq!(std::fs::read(&link).unwrap(), b"lib");
        }

        // Reinstall over an existing version.
        install_archive(&archive, &root, "v1").unwrap();
        assert!(bin.is_file());

        std::fs::remove_dir_all(&root).unwrap();
    }

    #[test]
    fn prune_keeps_only_current_version() {
        let root = temp_dir();
        for d in ["v1", "v2", "v2.partial"] {
            std::fs::create_dir_all(root.join(d)).unwrap();
        }
        std::fs::write(root.join("v1.tar.gz.download"), b"x").unwrap();

        prune_other_versions(&root, "v2");

        let mut left: Vec<_> = std::fs::read_dir(&root)
            .unwrap()
            .map(|e| e.unwrap().file_name().into_string().unwrap())
            .collect();
        left.sort();
        assert_eq!(left, vec!["v2"]);
        std::fs::remove_dir_all(&root).unwrap();
    }
}
