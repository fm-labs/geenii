// Typed IPC bindings for the desktop shell (src-tauri/src/server.rs).
import { invoke } from '@tauri-apps/api/core'
import { listen, UnlistenFn } from '@tauri-apps/api/event'

/** Mirrors `server::DesktopInfo`. */
export type DesktopInfo = {
  appName: string
  appVersion: string
  tauriVersion: string
  os: string
  arch: string
  /** Pinned server release, e.g. "v0.4.0.dev6". */
  serverVersion: string
  serverUrl: string
  serverBinOverride: string | null
  serverLog: string | null
}

/** Mirrors `server::ServerStatus` (serde tag "state", kebab-case). */
export type ServerStatus =
  | { state: 'idle' }
  | { state: 'disabled' }
  | { state: 'checking' }
  | { state: 'downloading'; downloaded: number; total: number | null }
  | { state: 'installing' }
  | { state: 'starting' }
  | { state: 'ready'; external: boolean }
  | { state: 'failed'; error: string }
  | { state: 'stopped' }

/** Human-readable label and indicator color (Tailwind class) for a server status. */
export const describeServerStatus = (status: ServerStatus | null): { label: string; dot: string; busy: boolean } => {
  switch (status?.state) {
    case 'ready':
      return { label: status.external ? 'Server running (external)' : 'Server running', dot: 'bg-emerald-500', busy: false }
    case 'downloading':
      return {
        label: status.total
          ? `Downloading server ${Math.round((status.downloaded / status.total) * 100)}%`
          : 'Downloading server',
        dot: 'bg-amber-500',
        busy: true,
      }
    case 'checking':
    case 'installing':
    case 'starting':
      return { label: `Server ${status.state}`, dot: 'bg-amber-500', busy: true }
    case 'failed':
      return { label: `Server failed: ${status.error}`, dot: 'bg-destructive', busy: false }
    case 'stopped':
      return { label: 'Server stopped', dot: 'bg-muted-foreground', busy: false }
    default:
      return { label: 'Server not started', dot: 'bg-muted-foreground', busy: false }
  }
}

export const SERVER_STATUS_EVENT = 'server-status'

/** IPC round trip to the Rust side; doubles as the connection check. */
export function getDesktopInfo(): Promise<DesktopInfo> {
  return invoke<DesktopInfo>('desktop_info')
}

export function getServerStatus(): Promise<ServerStatus> {
  return invoke<ServerStatus>('server_status')
}

export function startServer(): Promise<void> {
  return invoke<void>('server_start')
}

/** SIGTERM, then SIGKILL after a grace period. Only affects a server the app started. */
export function stopServer(): Promise<void> {
  return invoke<void>('server_stop')
}

export function restartServer(): Promise<void> {
  return invoke<void>('server_restart')
}

export function onServerStatus(handler: (status: ServerStatus) => void): Promise<UnlistenFn> {
  return listen<ServerStatus>(SERVER_STATUS_EVENT, (event) => handler(event.payload))
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
