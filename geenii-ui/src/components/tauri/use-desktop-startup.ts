import React from 'react'
import {
  DesktopInfo,
  getDesktopInfo,
  getServiceStatus,
  onServiceStatus,
  restartService,
  ServiceName,
  ServiceStatus,
  withTimeout,
} from './desktop-runtime.ts'

const IPC_TIMEOUT_MS = 5000
const BACKEND_TIMEOUT_MS = 5000
const BACKEND_ATTEMPTS = 5
const BACKEND_RETRY_DELAY_MS = 1000

/** Subset of the server's `/api/v1/info` response the loader shows. */
export type BackendInfo = {
  app?: { version?: string; cwd?: string }
  providers?: { name: string; configured: boolean }[]
  [key: string]: unknown
}

type StepState = 'pending' | 'active' | 'done' | 'error'

export type DesktopStartup = {
  /** Step 1: IPC to the Tauri backend. */
  tauri: { state: StepState; info: DesktopInfo | null; error: string | null }
  /** Step 2: the server process managed by the Tauri backend. */
  server: { state: StepState; status: ServiceStatus | null }
  /** The daemon managed by the Tauri backend. Not a startup step: the app works without it. */
  daemon: { state: StepState; status: ServiceStatus | null }
  /** Step 3: the server's HTTP API. */
  backend: { state: StepState; info: BackendInfo | null; error: string | null }
  ready: boolean
  retryConnection: () => void
  restartServer: () => void
  restartDaemon: () => void
  retryBackend: () => void
}

/** States in which the server's API is worth probing. */
const serverUsable = (status: ServiceStatus | null) =>
  status?.state === 'ready' || status?.state === 'disabled'

function serviceStepState(status: ServiceStatus | null): StepState {
  if (!status) return 'pending'
  switch (status.state) {
    case 'ready':
    case 'disabled':
      return 'done'
    case 'failed':
    case 'stopped':
      return 'error'
    default:
      return 'active'
  }
}

async function fetchBackendInfo(serverUrl: string, signal: AbortSignal): Promise<BackendInfo> {
  let lastError: unknown
  for (let attempt = 1; attempt <= BACKEND_ATTEMPTS; attempt++) {
    if (signal.aborted) throw new DOMException('Aborted', 'AbortError')
    // Per-attempt controller (AbortSignal.any is missing in older WebKit webviews).
    const attemptController = new AbortController()
    const abort = () => attemptController.abort()
    signal.addEventListener('abort', abort)
    const timer = setTimeout(abort, BACKEND_TIMEOUT_MS)
    try {
      const response = await fetch(`${serverUrl}/api/v1/info`, { signal: attemptController.signal })
      if (!response.ok) throw new Error(`HTTP ${response.status} ${response.statusText}`)
      return (await response.json()) as BackendInfo
    } catch (error) {
      if (signal.aborted) throw error
      lastError = error
      if (attempt < BACKEND_ATTEMPTS) {
        await new Promise((resolve) => setTimeout(resolve, BACKEND_RETRY_DELAY_MS))
      }
    } finally {
      clearTimeout(timer)
      signal.removeEventListener('abort', abort)
    }
  }
  throw lastError
}

/**
 * Live status of a service: subscribes to its status events first, then reads the
 * snapshot, so no transition is missed. A snapshot that arrives after an event is
 * older than it and is ignored.
 */
function useServiceStatus(
  service: ServiceName,
  enabled: boolean,
): [ServiceStatus | null, React.Dispatch<React.SetStateAction<ServiceStatus | null>>] {
  const [status, setStatus] = React.useState<ServiceStatus | null>(null)
  React.useEffect(() => {
    if (!enabled) return
    let cancelled = false
    let receivedEvent = false
    const unlisten = onServiceStatus(service, (next) => {
      receivedEvent = true
      if (!cancelled) setStatus(next)
    })
    unlisten
      .then(() => getServiceStatus(service))
      .then((snapshot) => {
        if (!cancelled && !receivedEvent) setStatus(snapshot)
      })
      .catch((error) => {
        if (!cancelled) setStatus({ state: 'failed', error: `${service} status: ${errorMessage(error)}` })
      })
    return () => {
      cancelled = true
      unlisten.then((stop) => stop()).catch(() => {})
    }
  }, [service, enabled])
  return [status, setStatus]
}

const errorMessage = (error: unknown) => (error instanceof Error ? error.message : String(error))

/**
 * Drives the desktop startup sequence:
 * Tauri IPC check -> server status (incl. download progress) -> backend API check.
 */
export function useDesktopStartup(): DesktopStartup {
  const [connectAttempt, setConnectAttempt] = React.useState(0)
  const [backendAttempt, setBackendAttempt] = React.useState(0)

  const [desktopInfo, setDesktopInfo] = React.useState<DesktopInfo | null>(null)
  const [tauriError, setTauriError] = React.useState<string | null>(null)
  const [backendInfo, setBackendInfo] = React.useState<BackendInfo | null>(null)
  const [backendError, setBackendError] = React.useState<string | null>(null)

  // 1. Connection check: a typed round trip through Tauri IPC.
  React.useEffect(() => {
    let cancelled = false
    setTauriError(null)
    withTimeout(getDesktopInfo(), IPC_TIMEOUT_MS, 'Tauri IPC')
      .then((info) => !cancelled && setDesktopInfo(info))
      .catch((error) => !cancelled && setTauriError(errorMessage(error)))
    return () => { cancelled = true }
  }, [connectAttempt])

  // 2. Service status (incl. download progress), once IPC works.
  const [status, setStatus] = useServiceStatus('server', !!desktopInfo)
  const [daemonStatus, setDaemonStatus] = useServiceStatus('daemon', !!desktopInfo)

  // 3. Backend check: once the server reports ready, ask its API for /info.
  const usable = serverUsable(status)
  React.useEffect(() => {
    setBackendInfo(null)
    setBackendError(null)
    if (!desktopInfo || !usable) return
    const controller = new AbortController()
    fetchBackendInfo(desktopInfo.serverUrl, controller.signal)
      .then(setBackendInfo)
      .catch((error) => !controller.signal.aborted && setBackendError(errorMessage(error)))
    return () => controller.abort()
  }, [desktopInfo, usable, backendAttempt])

  const retryConnection = React.useCallback(() => setConnectAttempt((n) => n + 1), [])
  const retryBackend = React.useCallback(() => setBackendAttempt((n) => n + 1), [])
  const restart = React.useCallback(() => {
    setStatus({ state: 'checking' })
    restartService('server').catch((error) =>
      setStatus({ state: 'failed', error: `restart: ${errorMessage(error)}` }),
    )
  }, [setStatus])
  const restartDaemon = React.useCallback(() => {
    setDaemonStatus({ state: 'checking' })
    restartService('daemon').catch((error) =>
      setDaemonStatus({ state: 'failed', error: `restart: ${errorMessage(error)}` }),
    )
  }, [setDaemonStatus])

  const tauriState: StepState = desktopInfo ? 'done' : tauriError ? 'error' : 'active'
  const serverState: StepState = desktopInfo ? serviceStepState(status) : 'pending'
  const backendState: StepState = !usable
    ? 'pending'
    : backendInfo ? 'done' : backendError ? 'error' : 'active'

  return {
    tauri: { state: tauriState, info: desktopInfo, error: tauriError },
    server: { state: serverState, status },
    daemon: { state: desktopInfo ? serviceStepState(daemonStatus) : 'pending', status: daemonStatus },
    backend: { state: backendState, info: backendInfo, error: backendError },
    ready: tauriState === 'done' && serverState === 'done' && backendState === 'done',
    retryConnection,
    restartServer: restart,
    restartDaemon,
    retryBackend,
  }
}
