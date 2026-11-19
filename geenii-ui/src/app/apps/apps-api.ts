import React from 'react'
import { openUrl } from '@tauri-apps/plugin-opener'
import { useApi } from '@/context/api-context.tsx'
import { AppContext } from '@/context/app-context.tsx'
import { joinUrl } from '@/lib/utils.ts'

/** Refresh interval of app lists and pages while the daemon is running */
export const APPS_POLL_MS = 5000
/** Refresh interval of an open app log */
export const APP_LOG_POLL_MS = 2000

export type AppType = 'statichtml' | 'python' | 'node' | 'binary'
/** null when the daemon is not running (the app info then comes from the files on disk) */
export type AppStatus = 'running' | 'starting' | 'error' | 'stopped' | null
export type AppAction = 'start' | 'stop' | 'restart'

/** An app with its runtime state, see `ProcessHost._app_info` in geenii/daemon/host.py */
export type GeeAppInfo = {
  name: string
  type: AppType
  title: string
  description: string | null
  version: string
  port: number | null
  path: string
  trusted: boolean
  sandbox: boolean
  /** Disabled apps can't be started and aren't autostarted (user settings) */
  enabled: boolean
  /** Started when the daemon starts or discovers the app (user settings, else the manifest) */
  autostart: boolean
  /** Added by its path (outside the app directories), see `useAddApp` */
  added: boolean
  /** The app's supervisor service, `app-<name>` */
  service: string
  status: AppStatus
  pid: number | null
  uptime_s: number | null
  /** Failures in a row; reset once it ran healthy */
  failures: number
  last_exit: { returncode: number, exited_at: number } | null
}

/** Response of GET /api/v1/apps/, see geenii/server/apps_routes.py */
export type AppsListResponse = {
  apps: GeeAppInfo[]
  daemon: { running: boolean }
}

export const appPath = (name: string) => `/api/v1/apps/${encodeURIComponent(name)}`

/** URL of the app's icon (its icon.svg, or a default one), for an <img> */
export const useAppIconUrl = (name: string): string => {
  const { apiBaseUrl } = useApi()
  return joinUrl(apiBaseUrl, `${appPath(name)}/icon`)
}

/** Message of a failed request (the server's Problem detail) */
export const requestError = (err: any): string => err?.response?.data?.detail || err?.message || 'Unknown error'

/** Whether the app has a process (running, or being (re)started by the supervisor) */
export const isActive = (app: GeeAppInfo) => app.status === 'running' || app.status === 'starting' || app.status === 'error'

/**
 * Load JSON from PATH, and reload it every APPS_POLL_MS while `active` and `poll(data)` are true.
 * `reload(quiet)`: quiet reloads keep the last data and error state (for polls and after actions).
 */
const usePolledJson = <T, >(path: string | null, poll: (data: T) => boolean, active = true) => {
  const { fetchJson } = useApi()
  const [data, setData] = React.useState<T | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [loading, setLoading] = React.useState(true)

  const reload = React.useCallback(async (quiet = false) => {
    if (!path) return
    if (!quiet) setLoading(true)
    try {
      setData(await fetchJson(path))
      setError(null)
    } catch (err) {
      if (!quiet) setError(requestError(err))
    } finally {
      if (!quiet) setLoading(false)
    }
  }, [fetchJson, path])

  React.useEffect(() => {
    setData(null)
    reload()
  }, [reload])

  const polling = active && data !== null && poll(data)
  React.useEffect(() => {
    if (!polling) return
    const id = setInterval(() => reload(true), APPS_POLL_MS)
    return () => clearInterval(id)
  }, [polling, reload])

  return { data, error, loading, reload }
}

/** All apps; polled while the daemon runs and `poll` is true (loaded once otherwise) */
export const useApps = (poll = true) => usePolledJson<AppsListResponse>('/api/v1/apps/', (d) => d.daemon.running, poll)

/** One app; polled while the daemon runs (status is null without it) */
export const useApp = (name: string | null) =>
  usePolledJson<GeeAppInfo>(name ? appPath(name) : null, (app) => app.status !== null)

/** Start, stop or restart an app; resolves to the app info after the action, throws on errors */
export const useAppAction = () => {
  const { fetchJson } = useApi()
  return React.useCallback(async (name: string, action: AppAction, port?: number | null): Promise<GeeAppInfo> => {
    const init: RequestInit = { method: 'POST' }
    if (action !== 'stop' && port) {
      init.headers = { 'Content-Type': 'application/json' }
      init.body = JSON.stringify({ port })
    }
    return await fetchJson(`${appPath(name)}/${action}`, init)
  }, [fetchJson])
}

/** App settings saved in the user settings file by the daemon */
export type AppSetting = 'enabled' | 'autostart'

/** Set an app setting; resolves to the app info, throws on errors */
export const useSetAppSetting = () => {
  const { fetchJson } = useApi()
  return React.useCallback(async (name: string, setting: AppSetting, value: boolean): Promise<GeeAppInfo> => {
    return await fetchJson(`${appPath(name)}/${setting}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ [setting]: value }),
    })
  }, [fetchJson])
}

/** Add an app directory with a manifest.json by its absolute path (disabled); resolves to the app info, throws on errors */
export const useAddApp = () => {
  const { fetchJson } = useApi()
  return React.useCallback(async (path: string): Promise<GeeAppInfo> => {
    return await fetchJson('/api/v1/apps/add', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path }),
    })
  }, [fetchJson])
}

/** URL a running app serves on: the API server's host (the daemon runs next to it) and the app's port */
export const useAppUrl = (app: GeeAppInfo | null): string | null => {
  const { apiBaseUrl } = useApi()
  if (!app?.port) return null
  let host = 'localhost'
  try {
    host = new URL(apiBaseUrl).hostname || host
  } catch {
    // relative or invalid base url: same machine
  }
  return `http://${host}:${app.port}/`
}

/** Open URL outside the UI: the system browser in the desktop app, a new tab in the web UI */
export const useOpenExternal = () => {
  const { isTauri } = React.useContext(AppContext) ?? { isTauri: false }
  return React.useCallback(async (url: string) => {
    if (isTauri) {
      await openUrl(url)
    } else {
      window.open(url, '_blank', 'noopener,noreferrer')
    }
  }, [isTauri])
}
