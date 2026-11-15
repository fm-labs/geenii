// Typed IPC bindings for the desktop shell (src-tauri/src/server.rs).
import { invoke } from '@tauri-apps/api/core'
import { listen, UnlistenFn } from '@tauri-apps/api/event'

/** A background process the desktop app manages (`server::Service`). */
export type ServiceName = 'server' | 'daemon'

export const SERVICE_LABELS: Record<ServiceName, string> = { server: 'Server', daemon: 'Daemon' }

/** Mirrors `server::DesktopInfo`. */
export type DesktopInfo = {
  appName: string
  appVersion: string
  tauriVersion: string
  os: string
  arch: string
  /** Pinned server release, e.g. "v0.4.0.dev6" (the daemon runs from the same binary). */
  serverVersion: string
  serverUrl: string
  serverBinOverride: string | null
  serverLog: string | null
  /** Unix socket of the daemon; passed to both services as GEENII_SOCKET. */
  daemonSocket: string | null
  daemonLog: string | null
}

/** Mirrors `server::ServiceStatus` (serde tag "state", kebab-case). */
export type ServiceStatus =
  | { state: 'idle' }
  | { state: 'disabled' } // autostart off (GEENII_DESKTOP_DEV_MODE=true)
  | { state: 'checking' }
  | { state: 'downloading'; downloaded: number; total: number | null }
  | { state: 'installing' }
  | { state: 'starting' }
  | { state: 'ready'; external: boolean }
  | { state: 'failed'; error: string }
  | { state: 'stopped' }

/** @deprecated use ServiceStatus */
export type ServerStatus = ServiceStatus

/** Human-readable label and indicator color (Tailwind class) for a service status. */
export const describeServiceStatus = (
  status: ServiceStatus | null,
  service: ServiceName = 'server',
): { label: string; dot: string; busy: boolean } => {
  const noun = SERVICE_LABELS[service]
  switch (status?.state) {
    case 'ready':
      return { label: status.external ? `${noun} running (external)` : `${noun} running`, dot: 'bg-emerald-500', busy: false }
    case 'downloading':
      return {
        // Both services run from the same release; whichever starts first downloads it.
        label: status.total
          ? `Downloading geenii ${Math.round((status.downloaded / status.total) * 100)}%`
          : 'Downloading geenii',
        dot: 'bg-amber-500',
        busy: true,
      }
    case 'checking':
    case 'installing':
    case 'starting':
      return { label: `${noun} ${status.state}`, dot: 'bg-amber-500', busy: true }
    case 'failed':
      return { label: `${noun} failed: ${status.error}`, dot: 'bg-destructive', busy: false }
    case 'stopped':
      return { label: `${noun} stopped`, dot: 'bg-muted-foreground', busy: false }
    default:
      return { label: `${noun} not started`, dot: 'bg-muted-foreground', busy: false }
  }
}

export const SERVER_STATUS_EVENT = 'server-status'
export const DAEMON_STATUS_EVENT = 'daemon-status'

/** IPC round trip to the Rust side; doubles as the connection check. */
export function getDesktopInfo(): Promise<DesktopInfo> {
  return invoke<DesktopInfo>('desktop_info')
}

export function getServiceStatus(service: ServiceName): Promise<ServiceStatus> {
  return invoke<ServiceStatus>(`${service}_status`)
}

export function startService(service: ServiceName): Promise<void> {
  return invoke<void>(`${service}_start`)
}

/** SIGTERM, then SIGKILL after a grace period. Only affects an instance the app started. */
export function stopService(service: ServiceName): Promise<void> {
  return invoke<void>(`${service}_stop`)
}

export function restartService(service: ServiceName): Promise<void> {
  return invoke<void>(`${service}_restart`)
}

/** The last `lines` lines of the service's log (max 1000); empty if there is none yet. */
export function getServiceLog(service: ServiceName, lines = 200): Promise<string> {
  return invoke<string>(`${service}_log`, { lines })
}

export function onServiceStatus(service: ServiceName, handler: (status: ServiceStatus) => void): Promise<UnlistenFn> {
  return listen<ServiceStatus>(`${service}-status`, (event) => handler(event.payload))
}

export function withTimeout<T>(promise: Promise<T>, ms: number, what: string): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`${what} timed out after ${ms / 1000}s`)), ms)
    promise.then(
      (value) => { clearTimeout(timer); resolve(value) },
      (error) => { clearTimeout(timer); reject(error) },
    )
  })
}
