//! Background geenii services: the HTTP server and the daemon (process manager,
//! scheduler, supervisor). Both run from the same pinned geenii binary.
//!
//! On startup the app makes sure each service is up:
//!
//! 0. Stop instances this app started that outlived it (see `stop_orphans`).
//! 1. If the service already answers (server: `/api/v1/health` on the pinned port;
//!    daemon: `ping` on its Unix socket), use it.
//! 2. Otherwise install the pinned PyInstaller onedir release (see
//!    `server-release.json`) into `$AppCache/server/<version>/`, downloading it
//!    from GitHub once and verifying its SHA-256 against the pinned checksum.
//!    Both services share the install; it runs once at a time.
//! 3. Spawn `<install>/geenii/geenii server start ...` / `... daemon start` and wait
//!    until it answers.
//!
//! Progress is published as `server-status` / `daemon-status` events (and the
//! `server_status` / `daemon_status` commands). The app passes `GEENII_SOCKET` to
//! both, so the server talks to the daemon this app checks.
//!
//! `GEENII_SERVER_BIN=/path/to/geenii` skips the download and runs that binary
//! instead. In dev mode with `GEENII_DESKTOP_DEV_MODE=true` neither service is
//! started automatically.

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
const DEV_MODE_ENV: &str = "GEENII_DESKTOP_DEV_MODE";
/// Daemon socket overrides, checked in this order (as in geenii.daemon.client).
const SOCKET_ENV_VARS: [&str; 2] = ["GEENII_SOCKET", "GEENII_PM_SOCKET"];
pub const STATUS_EVENT: &str = "server-status";
pub const DAEMON_STATUS_EVENT: &str = "daemon-status";
const STARTUP_TIMEOUT: Duration = Duration::from_secs(60);
/// How long a stopping service gets to shut down after SIGTERM before it is killed.
const STOP_GRACE: Duration = Duration::from_secs(5);

fn default_daemon_args() -> Vec<String> {
    vec!["daemon".into(), "start".into()]
}

#[derive(Debug, Deserialize)]
struct ReleaseManifest {
    version: String,
    url: String,
    binary: String,
    /// Server arguments.
    args: Vec<String>,
    #[serde(default = "default_daemon_args")]
    daemon_args: Vec<String>,
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

/// A background process the app manages.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Service {
    Server,
    Daemon,
}

impl Service {
    pub const ALL: [Service; 2] = [Service::Server, Service::Daemon];

    pub fn name(self) -> &'static str {
        match self {
            Service::Server => "server",
            Service::Daemon => "daemon",
        }
    }

    pub fn label(self) -> &'static str {
        match self {
            Service::Server => "Server",
            Service::Daemon => "Daemon",
        }
    }

    pub fn status_event(self) -> &'static str {
        match self {
            Service::Server => STATUS_EVENT,
            Service::Daemon => DAEMON_STATUS_EVENT,
        }
    }

    fn args(self, manifest: &ReleaseManifest) -> Vec<String> {
        match self {
            Service::Server => manifest.args.clone(),
            Service::Daemon => manifest.daemon_args.clone(),
        }
    }
}

#[derive(Clone, Debug, Default, Serialize)]
#[serde(tag = "state", rename_all = "kebab-case")]
pub enum ServiceStatus {
    #[default]
    Idle,
    /// Not started automatically (dev mode with GEENII_DESKTOP_DEV_MODE=true).
    Disabled,
    Checking,
    Downloading { downloaded: u64, total: Option<u64> },
    Installing,
    Starting,
    /// `external`: an instance was already running and is used as is.
    Ready { external: bool },
    Failed { error: String },
    Stopped,
}

impl ServiceStatus {
    /// A short, human-readable state, e.g. "running" or "downloading 42%".
    pub fn summary(&self) -> String {
        match self {
            ServiceStatus::Idle => "not started".into(),
            ServiceStatus::Disabled => "autostart off".into(),
            ServiceStatus::Checking => "checking…".into(),
            ServiceStatus::Downloading { downloaded, total: Some(total) } if *total > 0 => {
                format!("downloading {}%", downloaded.saturating_mul(100) / total)
            }
            ServiceStatus::Downloading { .. } => "downloading…".into(),
            ServiceStatus::Installing => "installing…".into(),
            ServiceStatus::Starting => "starting…".into(),
            ServiceStatus::Ready { external: false } => "running".into(),
            ServiceStatus::Ready { external: true } => "running (external)".into(),
            ServiceStatus::Failed { .. } => "failed".into(),
            ServiceStatus::Stopped => "stopped".into(),
        }
    }
}

/// "Server: running", for menus.
pub fn status_text(app: &AppHandle, service: Service) -> String {
    let status = state(app, service).status.lock().unwrap().summary();
    format!("{}: {status}", service.label())
}

/// A process this app started.
struct ManagedChild {
    child: CommandChild,
    /// Set by the output task when the process has terminated.
    exited: Arc<AtomicBool>,
}

#[derive(Default)]
struct ServiceState {
    child: Mutex<Option<ManagedChild>>,
    status: Mutex<ServiceStatus>,
    busy: AtomicBool,
}

#[derive(Default)]
pub struct Services {
    server: ServiceState,
    daemon: ServiceState,
    /// Serializes installing the release, which both services need.
    install: tauri::async_runtime::Mutex<()>,
}

fn services(app: &AppHandle) -> &Services {
    app.state::<Services>().inner()
}

fn state(app: &AppHandle, service: Service) -> &ServiceState {
    let services = services(app);
    match service {
        Service::Server => &services.server,
        Service::Daemon => &services.daemon,
    }
}

fn set_status(app: &AppHandle, service: Service, status: ServiceStatus) {
    println!("{} status: {status:?}", service.name());
    *state(app, service).status.lock().unwrap() = status.clone();
    let _ = app.emit(service.status_event(), status);
}

/// Starts the server and the daemon on app startup, unless running in dev mode with
/// `GEENII_DESKTOP_DEV_MODE=true` (then they are started manually, e.g. from the panel).
pub fn autostart(app: &AppHandle) {
    let skip = tauri::is_dev() && std::env::var(DEV_MODE_ENV).is_ok_and(|v| v == "true");
    for service in Service::ALL {
        if skip {
            println!("Dev mode ({DEV_MODE_ENV}=true): not starting the {}.", service.name());
            set_status(app, service, ServiceStatus::Disabled);
        } else {
            start_service(app, service);
        }
    }
}

/// Starts a service in the background. No-op while a start is already in progress.
pub fn start_service(app: &AppHandle, service: Service) {
    if state(app, service).busy.swap(true, Ordering::SeqCst) {
        return;
    }
    let app = app.clone();
    tauri::async_runtime::spawn(async move {
        // Run in its own task so a panic is reported instead of leaving `busy` set.
        let task_app = app.clone();
        let result = tauri::async_runtime::spawn(async move { run(&task_app, service).await })
            .await
            .unwrap_or_else(|e| Err(format!("{} startup task crashed: {e}", service.name())));
        if let Err(error) = result {
            eprintln!("{} startup failed: {error}", service.name());
            set_status(&app, service, ServiceStatus::Failed { error });
        }
        state(&app, service).busy.store(false, Ordering::SeqCst);
    });
}

/// Stops the service process this app started (an external one is left alone):
/// SIGTERM so it can shut down cleanly (and stop its own children), then SIGKILL
/// if it is still running after `STOP_GRACE`. Blocks for at most `STOP_GRACE`.
pub fn stop_service(app: &AppHandle, service: Service) {
    let managed = state(app, service).child.lock().unwrap().take();
    if let Some(managed) = managed {
        terminate(service, managed);
        set_status(app, service, ServiceStatus::Stopped);
    }
}

/// Stops all services at once; blocks for at most `STOP_GRACE`.
pub fn stop_all(app: &AppHandle) {
    std::thread::scope(|scope| {
        for service in Service::ALL {
            scope.spawn(move || stop_service(app, service));
        }
    });
}

fn terminate(service: Service, ManagedChild { child, exited }: ManagedChild) {
    let pid = child.pid();
    let name = service.name();
    #[cfg(unix)]
    {
        println!("Stopping {name} (pid {pid}): SIGTERM");
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
        println!("{name} (pid {pid}) exited");
        return;
    }
    println!("Killing {name} (pid {pid})");
    if let Err(e) = child.kill() {
        eprintln!("failed to kill {name}: {e}");
    }
}

/// Stops instances of `service` this app started that outlived it: `tauri dev` restarts
/// and crashes skip the exit hook, and a leftover would otherwise be reused as an
/// "external" one, possibly an old version, with nobody owning its lifecycle or logs.
///
/// An instance is ours if it runs a binary from our install dir (or `GEENII_SERVER_BIN`)
/// with this service's subcommand, and orphaned if its parent is not a running instance
/// of this app (so the services of a second, live app instance are left alone).
#[cfg(unix)]
async fn stop_orphans(app: &AppHandle, service: Service, manifest: &ReleaseManifest) {
    let mut prefixes = Vec::new();
    if let Ok(cache) = app.path().app_cache_dir() {
        prefixes.push(format!("{}/", cache.join("server").display()));
    }
    if let Some(bin) = std::env::var_os(BIN_OVERRIDE_ENV) {
        prefixes.push(format!("{} ", PathBuf::from(bin).display()));
    }
    let subcommand = service.args(manifest).into_iter().take(2).collect::<Vec<_>>().join(" ");
    let Ok(app_exe) = std::env::current_exe() else { return };
    let app_exe = app_exe.display().to_string();

    let output = match tokio::process::Command::new("ps").args(["-axww", "-o", "pid=,ppid=,command="]).output().await {
        Ok(output) if output.status.success() => output,
        Ok(output) => return eprintln!("orphan check: ps failed: {}", output.status),
        Err(e) => return eprintln!("orphan check: ps failed: {e}"),
    };
    let orphans = find_orphans(&String::from_utf8_lossy(&output.stdout), &prefixes, &subcommand, &app_exe);
    if orphans.is_empty() {
        return;
    }
    let name = service.name();
    let _ = tauri::async_runtime::spawn_blocking(move || {
        for pid in orphans {
            stop_pid(name, pid);
        }
    })
    .await;
}

#[cfg(not(unix))]
async fn stop_orphans(_app: &AppHandle, _service: Service, _manifest: &ReleaseManifest) {}

/// Parses `ps -o pid=,ppid=,command=` output; returns the pids of our `subcommand`
/// processes (e.g. "daemon start") whose parent is not a running `app_exe`.
fn find_orphans(ps_output: &str, prefixes: &[String], subcommand: &str, app_exe: &str) -> Vec<u32> {
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
    let subcommand = format!(" {subcommand} ");
    procs
        .iter()
        .filter(|&&(_, _, cmd)| {
            let cmd = format!("{cmd} ");
            prefixes.iter().any(|prefix| cmd.starts_with(prefix.as_str())) && cmd.contains(&subcommand)
        })
        .filter(|&&(_, ppid, _)| !is_app(ppid))
        .map(|&(pid, _, _)| pid)
        .collect()
}

/// SIGTERM, wait up to STOP_GRACE, then SIGKILL; for a process that is not our child.
#[cfg(unix)]
fn stop_pid(name: &str, pid: u32) {
    let pid = pid as libc::pid_t;
    // SAFETY: kill(2) with a pid just read from ps; signal 0 only probes for existence.
    let alive = || unsafe { libc::kill(pid, 0) } == 0;
    println!("Stopping orphaned {name} (pid {pid}): SIGTERM");
    if unsafe { libc::kill(pid, libc::SIGTERM) } != 0 {
        return;
    }
    let deadline = Instant::now() + STOP_GRACE;
    while alive() && Instant::now() < deadline {
        std::thread::sleep(Duration::from_millis(50));
    }
    if alive() {
        println!("Killing orphaned {name} (pid {pid})");
        unsafe { libc::kill(pid, libc::SIGKILL) };
    } else {
        println!("Orphaned {name} (pid {pid}) exited");
    }
}

/// The daemon's socket, resolved like geenii.daemon.client.default_socket_path
/// (`$GEENII_SOCKET`, `$GEENII_PM_SOCKET`, else `$GEENII_CACHE_DIR/geeniid.sock`).
/// The app passes it to both services as `GEENII_SOCKET`.
fn daemon_socket_path(app: &AppHandle) -> Result<PathBuf, String> {
    let env = |name: &str| std::env::var_os(name).filter(|v| !v.is_empty());
    if let Some(path) = SOCKET_ENV_VARS.iter().find_map(|name| env(name)) {
        return Ok(PathBuf::from(path));
    }
    let cache = match env("GEENII_CACHE_DIR") {
        Some(dir) => PathBuf::from(dir),
        None => app.path().home_dir().map_err(|e| e.to_string())?.join(".cache").join("geenii"),
    };
    Ok(cache.join("geeniid.sock"))
}

// ---------------------------------------------------------------------------
// Commands

#[tauri::command]
pub fn server_status(app: AppHandle) -> ServiceStatus {
    state(&app, Service::Server).status.lock().unwrap().clone()
}

#[tauri::command]
pub fn daemon_status(app: AppHandle) -> ServiceStatus {
    state(&app, Service::Daemon).status.lock().unwrap().clone()
}

/// What the frontend needs to know about the desktop shell and its services.
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
    daemon_socket: Option<String>,
    daemon_log: Option<String>,
}

#[tauri::command]
pub fn desktop_info(app: AppHandle) -> Result<DesktopInfo, String> {
    let manifest = ReleaseManifest::load()?;
    let package = app.package_info();
    let display = |p: Result<PathBuf, String>| p.ok().map(|p| p.display().to_string());
    Ok(DesktopInfo {
        app_name: package.name.clone(),
        app_version: package.version.to_string(),
        tauri_version: tauri::VERSION,
        os: std::env::consts::OS,
        arch: std::env::consts::ARCH,
        server_version: manifest.version,
        server_url: format!("http://localhost:{}", manifest.port),
        server_bin_override: std::env::var(BIN_OVERRIDE_ENV).ok(),
        server_log: display(log_path(&app, Service::Server)),
        daemon_socket: display(daemon_socket_path(&app)),
        daemon_log: display(log_path(&app, Service::Daemon)),
    })
}

/// The last `lines` lines (at most 1000) of the server log; empty if there is no log yet.
#[tauri::command]
pub async fn server_log(app: AppHandle, lines: Option<usize>) -> Result<String, String> {
    tail_log(&app, Service::Server, lines).await
}

/// The last `lines` lines (at most 1000) of the daemon log; empty if there is no log yet.
#[tauri::command]
pub async fn daemon_log(app: AppHandle, lines: Option<usize>) -> Result<String, String> {
    tail_log(&app, Service::Daemon, lines).await
}

async fn tail_log(app: &AppHandle, service: Service, lines: Option<usize>) -> Result<String, String> {
    let path = log_path(app, service)?;
    let lines = lines.unwrap_or(200).min(1000);
    tauri::async_runtime::spawn_blocking(move || read_tail(&path, lines))
        .await
        .map_err(|e| e.to_string())?
}

/// Reads the last `max_lines` lines of a file, looking at no more than its last 256 KB.
fn read_tail(path: &Path, max_lines: usize) -> Result<String, String> {
    use std::io::{Read, Seek, SeekFrom};
    const MAX_BYTES: u64 = 256 * 1024;
    let mut file = match File::open(path) {
        Ok(file) => file,
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok(String::new()),
        Err(e) => return Err(format!("open {}: {e}", path.display())),
    };
    let len = file.metadata().map_err(|e| e.to_string())?.len();
    let start = len.saturating_sub(MAX_BYTES);
    file.seek(SeekFrom::Start(start)).map_err(|e| e.to_string())?;
    let mut bytes = Vec::new();
    file.read_to_end(&mut bytes).map_err(|e| e.to_string())?;
    let text = String::from_utf8_lossy(&bytes);
    let mut all: Vec<&str> = text.lines().collect();
    if start > 0 && !all.is_empty() {
        all.remove(0); // probably cut off mid-line
    }
    Ok(all[all.len().saturating_sub(max_lines)..].join("\n"))
}

fn log_path(app: &AppHandle, service: Service) -> Result<PathBuf, String> {
    Ok(app
        .path()
        .app_log_dir()
        .map_err(|e| e.to_string())?
        .join(format!("{}.log", service.name())))
}

#[tauri::command]
pub fn server_start(app: AppHandle) {
    start_service(&app, Service::Server);
}

#[tauri::command]
pub fn daemon_start(app: AppHandle) {
    start_service(&app, Service::Daemon);
}

/// Stops the server this app started (SIGTERM, then SIGKILL after STOP_GRACE).
/// A server the app did not start is left running.
#[tauri::command]
pub async fn server_stop(app: AppHandle) {
    stop_blocking(app, Service::Server).await;
}

/// Stops the daemon this app started (SIGTERM, then SIGKILL after STOP_GRACE).
/// The daemon stops the processes it manages. A daemon the app did not start is left running.
#[tauri::command]
pub async fn daemon_stop(app: AppHandle) {
    stop_blocking(app, Service::Daemon).await;
}

#[tauri::command]
pub async fn server_restart(app: AppHandle) {
    stop_blocking(app.clone(), Service::Server).await;
    start_service(&app, Service::Server);
}

#[tauri::command]
pub async fn daemon_restart(app: AppHandle) {
    stop_blocking(app.clone(), Service::Daemon).await;
    start_service(&app, Service::Daemon);
}

/// stop_service can block for up to STOP_GRACE.
async fn stop_blocking(app: AppHandle, service: Service) {
    let _ = tauri::async_runtime::spawn_blocking(move || stop_service(&app, service)).await;
}

// ---------------------------------------------------------------------------
// Startup

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

/// How to tell whether a service is up.
enum Probe {
    Http { client: reqwest::Client, url: String },
    Socket(PathBuf),
}

impl Probe {
    fn new(app: &AppHandle, service: Service, manifest: &ReleaseManifest) -> Result<Self, String> {
        Ok(match service {
            Service::Server => Probe::Http {
                client: reqwest::Client::builder()
                    .no_proxy()
                    .timeout(Duration::from_secs(1))
                    .build()
                    .map_err(|e| e.to_string())?,
                url: format!("http://127.0.0.1:{}/api/v1/health", manifest.port),
            },
            Service::Daemon => Probe::Socket(daemon_socket_path(app)?),
        })
    }

    async fn is_up(&self) -> bool {
        match self {
            Probe::Http { client, url } => matches!(client.get(url).send().await, Ok(r) if r.status().is_success()),
            Probe::Socket(path) => {
                let path = path.clone();
                tauri::async_runtime::spawn_blocking(move || ping_socket(&path))
                    .await
                    .unwrap_or(false)
            }
        }
    }
}

/// Sends the daemon's `ping` over its Unix socket (newline-delimited JSON).
#[cfg(unix)]
fn ping_socket(path: &Path) -> bool {
    use std::io::{BufRead, BufReader};
    use std::os::unix::net::UnixStream;
    let Ok(mut stream) = UnixStream::connect(path) else { return false };
    let _ = stream.set_read_timeout(Some(Duration::from_secs(1)));
    let _ = stream.set_write_timeout(Some(Duration::from_secs(1)));
    if stream.write_all(b"{\"method\":\"ping\"}\n").is_err() {
        return false;
    }
    let mut line = String::new();
    if BufReader::new(&stream).read_line(&mut line).is_err() {
        return false;
    }
    serde_json::from_str::<serde_json::Value>(&line).is_ok_and(|v| v["ok"] == true)
}

#[cfg(not(unix))]
fn ping_socket(_path: &Path) -> bool {
    false
}

async fn run(app: &AppHandle, service: Service) -> Result<(), String> {
    ensure_tls_provider();
    let manifest = ReleaseManifest::load()?;
    let probe = Probe::new(app, service, &manifest)?;
    let name = service.name();

    set_status(app, service, ServiceStatus::Checking);
    stop_orphans(app, service, &manifest).await;
    if probe.is_up().await {
        println!("A {name} is already running; using it.");
        set_status(app, service, ServiceStatus::Ready { external: true });
        return Ok(());
    }

    let bin = match std::env::var_os(BIN_OVERRIDE_ENV) {
        Some(path) => PathBuf::from(path),
        None => ensure_installed(app, service, &manifest).await?,
    };

    set_status(app, service, ServiceStatus::Starting);
    let (exited, log_path) = spawn(app, service, &bin, &service.args(&manifest))?;

    let deadline = Instant::now() + STARTUP_TIMEOUT;
    loop {
        if exited.load(Ordering::SeqCst) {
            return Err(format!("{name} exited during startup; see {}", log_path.display()));
        }
        if probe.is_up().await {
            set_status(app, service, ServiceStatus::Ready { external: false });
            return Ok(());
        }
        if Instant::now() > deadline {
            stop_blocking(app.clone(), service).await;
            return Err(format!(
                "{name} not ready after {}s; see {}",
                STARTUP_TIMEOUT.as_secs(),
                log_path.display()
            ));
        }
        tokio::time::sleep(Duration::from_millis(250)).await;
    }
}

/// Returns the geenii binary of the pinned release, installing it first if needed.
/// Progress is reported as `service`'s status.
async fn ensure_installed(app: &AppHandle, service: Service, manifest: &ReleaseManifest) -> Result<PathBuf, String> {
    let root = app
        .path()
        .app_cache_dir()
        .map_err(|e| e.to_string())?
        .join("server");
    let bin = root.join(&manifest.version).join(&manifest.binary);
    // The other service may be installing right now; wait for it, then re-check.
    let _install = services(app).install.lock().await;
    if bin.is_file() {
        return Ok(bin);
    }

    let target = target_tag()?;
    let expected = manifest.expected_sha256(target)?;
    std::fs::create_dir_all(&root).map_err(|e| format!("create {}: {e}", root.display()))?;

    let archive = root.join(format!("{}.tar.gz.download", manifest.version));
    download(app, service, &manifest.archive_url(target), &archive, &expected).await?;

    set_status(app, service, ServiceStatus::Installing);
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
async fn download(app: &AppHandle, service: Service, url: &str, dest: &Path, expected: &str) -> Result<(), String> {
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
    set_status(app, service, ServiceStatus::Downloading { downloaded, total });

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
                set_status(app, service, ServiceStatus::Downloading { downloaded, total });
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

/// Spawns a service and forwards its output to its log file.
/// Returns a flag set when the process terminates, and the log path.
fn spawn(app: &AppHandle, service: Service, bin: &Path, args: &[String]) -> Result<(Arc<AtomicBool>, PathBuf), String> {
    let name = service.name();
    let log_path = log_path(app, service)?;
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
    // Run in the user's home directory (GEENII_WORKING_DIR defaults to the cwd).
    // PyInstaller locates its bundled files relative to the executable, not the cwd.
    match app.path().home_dir() {
        Ok(home) => command = command.current_dir(home),
        Err(e) => eprintln!("no home directory ({e}); starting {name} in the current directory"),
    }
    // `geenii` in commands the services run (e.g. scheduler tasks) is this binary:
    // apps started from the GUI do not have it on their PATH.
    if let Some(dir) = bin.parent() {
        let inherited = std::env::var_os("PATH").unwrap_or_default();
        let paths = std::iter::once(dir.to_path_buf()).chain(std::env::split_paths(&inherited));
        match std::env::join_paths(paths) {
            Ok(path) => command = command.env("PATH", path.to_string_lossy().to_string()),
            Err(e) => eprintln!("cannot add {} to PATH: {e}", dir.display()),
        }
    }
    // The server finds the daemon on the socket the app checks.
    match daemon_socket_path(app) {
        Ok(socket) => command = command.env("GEENII_SOCKET", socket.to_string_lossy().to_string()),
        Err(e) => eprintln!("no daemon socket path ({e})"),
    }
    let (mut rx, child) = command
        .spawn()
        .map_err(|e| format!("failed to start {}: {e}", bin.display()))?;
    let pid = child.pid();
    println!("{name} started (pid {pid})");
    let exited = Arc::new(AtomicBool::new(false));
    let exited_flag = exited.clone();
    *state(app, service).child.lock().unwrap() = Some(ManagedChild {
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
                    eprintln!("{name} error: {err}");
                    let _ = writeln!(log, "{} ERROR: {err}", name.to_uppercase());
                }
                CommandEvent::Terminated(p) => {
                    let msg = format!("{name} terminated: code={:?} signal={:?}", p.code, p.signal);
                    eprintln!("{msg}");
                    let _ = writeln!(log, "{msg}");
                    exited_flag.store(true, Ordering::SeqCst);
                    // Still registered => not stopped by us: report the crash.
                    // (Compare pids: after a restart the slot holds the new process.)
                    let crashed = {
                        let mut slot = state(&app, service).child.lock().unwrap();
                        if slot.as_ref().is_some_and(|m| m.child.pid() == pid) {
                            slot.take();
                            true
                        } else {
                            false
                        }
                    };
                    if crashed {
                        set_status(&app, service, ServiceStatus::Failed { error: msg });
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
        let json = |s: ServiceStatus| serde_json::to_value(s).unwrap();
        assert_eq!(json(ServiceStatus::Idle), serde_json::json!({"state": "idle"}));
        assert_eq!(
            json(ServiceStatus::Downloading { downloaded: 5, total: None }),
            serde_json::json!({"state": "downloading", "downloaded": 5, "total": null})
        );
        assert_eq!(json(ServiceStatus::Ready { external: true }), serde_json::json!({"state": "ready", "external": true}));
        assert_eq!(
            json(ServiceStatus::Failed { error: "x".into() }),
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
            daemon_socket: None,
            daemon_log: None,
        })
        .unwrap();
        let mut keys: Vec<_> = info.as_object().unwrap().keys().cloned().collect();
        keys.sort();
        assert_eq!(
            keys,
            [
                "appName", "appVersion", "arch", "daemonLog", "daemonSocket", "os", "serverBinOverride", "serverLog",
                "serverUrl", "serverVersion", "tauriVersion"
            ]
        );
    }

    #[test]
    fn find_orphans_matches_only_our_parentless_services() {
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
          300     1 /Cache/io.geenii.desktop/server/v1/geenii/geenii daemon start
          301   100 /Cache/io.geenii.desktop/server/v1/geenii/geenii daemon start
        ";
        // 200: orphaned (parent launchd); 202: parent gone. 201: live app instance.
        // 203/204/205: not our binaries. 300/301: daemons, not servers.
        assert_eq!(find_orphans(ps, &prefixes, "server start", app), vec![200, 202]);
        // 300: orphaned daemon; 301: the live app's daemon.
        assert_eq!(find_orphans(ps, &prefixes, "daemon start", app), vec![300]);
    }

    #[test]
    fn status_summary_is_short() {
        assert_eq!(ServiceStatus::Ready { external: false }.summary(), "running");
        assert_eq!(ServiceStatus::Downloading { downloaded: 21, total: Some(50) }.summary(), "downloading 42%");
        assert_eq!(ServiceStatus::Downloading { downloaded: 5, total: Some(0) }.summary(), "downloading…");
        assert_eq!(ServiceStatus::Failed { error: "long error".into() }.summary(), "failed");
    }

    #[test]
    fn manifest_defaults_daemon_args() {
        assert_eq!(ReleaseManifest::load().unwrap().daemon_args, ["daemon", "start"]);
    }

    #[cfg(unix)]
    #[test]
    fn ping_socket_expects_ok_reply() {
        use std::io::{BufRead, BufReader};
        use std::os::unix::net::UnixListener;
        // Unix socket paths are limited to ~104 bytes; macOS's temp dir is long.
        let path = PathBuf::from(format!("/tmp/geenii-ping-{}.sock", std::process::id()));
        let _ = std::fs::remove_file(&path);
        assert!(!ping_socket(&path), "no socket");

        let listener = UnixListener::bind(&path).unwrap();
        let server = std::thread::spawn(move || {
            for reply in [&b"{\"ok\":true,\"result\":\"pong\"}\n"[..], b"{\"ok\":false,\"error\":\"x\"}\n"] {
                let (mut conn, _) = listener.accept().unwrap();
                let mut line = String::new();
                BufReader::new(&conn).read_line(&mut line).unwrap();
                assert_eq!(line, "{\"method\":\"ping\"}\n");
                conn.write_all(reply).unwrap();
            }
        });
        assert!(ping_socket(&path));
        assert!(!ping_socket(&path));
        server.join().unwrap();
        std::fs::remove_file(&path).unwrap();
    }

    #[test]
    fn read_tail_returns_last_lines() {
        let dir = temp_dir();
        let path = dir.join("server.log");
        assert_eq!(read_tail(&path, 5).unwrap(), "");
        std::fs::write(&path, "a\nb\nc\nd\n").unwrap();
        assert_eq!(read_tail(&path, 2).unwrap(), "c\nd");
        assert_eq!(read_tail(&path, 10).unwrap(), "a\nb\nc\nd");
        // Larger than the read window: the partial first line is dropped.
        let big: String = (0..40_000).map(|i| format!("line {i}\n")).collect();
        std::fs::write(&path, &big).unwrap();
        assert_eq!(read_tail(&path, 2).unwrap(), "line 39998\nline 39999");
        let window = read_tail(&path, 1000).unwrap();
        assert!(window.lines().all(|l| l.starts_with("line ")));
        std::fs::remove_dir_all(&dir).unwrap();
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
