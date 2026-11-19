import React from 'react'
import { LoaderIcon, PlayIcon, RotateCwIcon, SquareIcon } from 'lucide-react'
import { Badge } from '@/components/ui/badge.tsx'
import { Button } from '@/components/ui/button.tsx'
import { Switch } from '@/components/ui/switch.tsx'
import { useApi } from '@/context/api-context.tsx'
import { cn } from 'cn'
import {
  APP_LOG_POLL_MS, AppAction, appPath, AppSetting, GeeAppInfo, isActive, requestError, useAppAction, useSetAppSetting,
} from '@/app/apps/apps-api.ts'

export const fmtUptime = (s: number | null) => {
  if (s == null) return '—'
  if (s < 60) return `${Math.round(s)}s`
  if (s < 3600) return `${Math.floor(s / 60)}m ${Math.round(s % 60)}s`
  if (s < 86400) return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`
  return `${Math.floor(s / 86400)}d ${Math.floor((s % 86400) / 3600)}h`
}

const STATUS_DOT: Record<string, { className: string, label: string }> = {
  running: { className: 'bg-emerald-500', label: 'Running' },
  starting: { className: 'bg-amber-400 animate-pulse', label: 'Starting' },
  error: { className: 'bg-red-500', label: 'Failing; the supervisor keeps restarting it' },
  stopped: { className: 'bg-zinc-400 dark:bg-zinc-500', label: 'Stopped' },
  disabled: { className: 'border-2 border-zinc-400 bg-transparent', label: 'Disabled' },
  unknown: { className: 'border-2 border-dashed border-zinc-400 bg-transparent', label: 'Unknown: the geenii daemon is not running' },
}

/** A colored dot for the app's status: green running, amber starting, red failing, grey stopped, hollow disabled/unknown */
export const AppStatusDot = ({ app, className }: { app: GeeAppInfo, className?: string }) => {
  const key = app.status === null ? 'unknown' : app.status === 'stopped' && !app.enabled ? 'disabled' : app.status
  const dot = STATUS_DOT[key]
  return (
    <span
      role="img"
      aria-label={dot.label}
      title={dot.label}
      className={cn('inline-block size-2.5 shrink-0 rounded-full', dot.className, className)}
    />
  )
}

export const AppStatusBadge = ({ app }: { app: GeeAppInfo }) => {
  switch (app.status) {
    case 'running':
      return (
        <Badge variant="secondary" className="gap-1.5">
          <span className="size-1.5 rounded-full bg-emerald-500" /> running
        </Badge>
      )
    case 'starting':
      return <Badge variant="outline" className="gap-1 text-amber-600"><LoaderIcon className="size-3 animate-spin" /> starting</Badge>
    case 'error':
      return <Badge variant="destructive" title={`${app.failures} failure(s) in a row`}>error</Badge>
    case 'stopped':
      return app.enabled
        ? <Badge variant="outline">stopped</Badge>
        : <Badge variant="outline" className="text-muted-foreground" title="Enable it in the console app settings">disabled</Badge>
    default:
      return <Badge variant="outline" className="text-muted-foreground" title="The geenii daemon is not running">unknown</Badge>
  }
}

/**
 * Start/stop/restart buttons. `onDone(message, warn)` reports the outcome; the parent
 * reloads its data (the status changes asynchronously, so it should reload again shortly after).
 */
export const AppControls = ({ app, onDone, size = 'sm' }: {
  app: GeeAppInfo
  onDone: (message: string, warn?: boolean) => void
  size?: 'sm' | 'xs'
}) => {
  const runAction = useAppAction()
  const [busy, setBusy] = React.useState<AppAction | null>(null)
  const daemonRunning = app.status !== null
  const active = isActive(app)

  const act = async (action: AppAction) => {
    setBusy(action)
    try {
      const info = await runAction(app.name, action)
      const verb = action === 'start' ? 'Started' : action === 'stop' ? 'Stopped' : 'Restarted'
      onDone(`${verb} "${app.title}"${action !== 'stop' && info.port ? ` on port ${info.port}` : ''}.`)
    } catch (err) {
      onDone(`Could not ${action} "${app.title}": ${requestError(err)}`, true)
    } finally {
      setBusy(null)
    }
  }

  const reason = !daemonRunning
    ? 'The geenii daemon is not running (start it with `geenii daemon start`)'
    : !app.enabled ? 'The app is disabled; enable it in the console app settings' : undefined
  const icon = (action: AppAction, Icon: typeof PlayIcon) =>
    busy === action ? <LoaderIcon className="animate-spin" /> : <Icon />

  return (
    <div className="flex flex-wrap gap-2">
      {!active ? (
        <span title={reason ?? 'Run the app as a background service of the daemon'}>
          <Button size={size} onClick={() => act('start')} disabled={!daemonRunning || !app.enabled || !!busy}>
            {icon('start', PlayIcon)} Start
          </Button>
        </span>
      ) : (
        <>
          <Button size={size} variant="outline" onClick={() => act('stop')} disabled={!!busy}>
            {icon('stop', SquareIcon)} Stop
          </Button>
          <span title="Restart with the current manifest">
            <Button size={size} variant="outline" onClick={() => act('restart')} disabled={!!busy}>
              {icon('restart', RotateCwIcon)} Restart
            </Button>
          </span>
        </>
      )}
    </div>
  )
}

const SETTING_TEXT: Record<AppSetting, { label: string, title: string, on: string, off: string }> = {
  enabled: {
    label: 'Enabled',
    title: "Disabled apps can't be started and aren't autostarted",
    on: 'is enabled',
    off: 'is disabled and stopped',
  },
  autostart: {
    label: 'Autostart',
    title: 'Start the app whenever the daemon starts',
    on: 'will start with the daemon from its next start',
    off: 'will no longer start with the daemon',
  },
}

/**
 * Switch for an app setting, saved in the user settings by the daemon. Shows the new value
 * right away; `onDone(message, warn)` reports the outcome (the parent reloads its data).
 */
export const AppSettingToggle = ({ app, setting, onDone }: {
  app: GeeAppInfo
  setting: AppSetting
  onDone: (message: string, warn?: boolean) => void
}) => {
  const setAppSetting = useSetAppSetting()
  // The value being saved, shown until the reloaded app info has it
  const [pending, setPending] = React.useState<boolean | null>(null)
  const daemonRunning = app.status !== null
  const current = app[setting]
  const checked = pending ?? current
  const text = SETTING_TEXT[setting]

  React.useEffect(() => {
    if (pending !== null && current === pending) setPending(null)
  }, [current, pending])

  const toggle = async (value: boolean) => {
    setPending(value)
    try {
      await setAppSetting(app.name, setting, value)
      onDone(`"${app.title}" ${value ? text.on : text.off}.`)
    } catch (err) {
      setPending(null)
      onDone(`Could not change "${text.label}" of "${app.title}": ${requestError(err)}`, true)
    }
  }

  return (
    <label className={cn('flex items-center gap-2 text-sm', !daemonRunning && 'opacity-60')}
           title={daemonRunning ? text.title : 'The geenii daemon is not running'}>
      <Switch checked={checked} onCheckedChange={toggle} disabled={!daemonRunning || pending !== null} />
      {text.label}
    </label>
  )
}

/** Recent output of an app, re-read while shown */
export const AppLog = ({ name, className }: { name: string, className?: string }) => {
  const { fetchJson } = useApi()
  const [lines, setLines] = React.useState<string[] | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const preRef = React.useRef<HTMLPreElement>(null)

  React.useEffect(() => {
    let cancelled = false
    const pull = async () => {
      const pre = preRef.current
      const atBottom = !pre || pre.scrollTop + pre.clientHeight >= pre.scrollHeight - 4
      try {
        const res = await fetchJson(`${appPath(name)}/logs?tail=500`)
        if (cancelled) return
        setLines(res.lines)
        setError(null)
        // Stay at the bottom, unless the user scrolled up
        if (atBottom) requestAnimationFrame(() => preRef.current && (preRef.current.scrollTop = preRef.current.scrollHeight))
      } catch (err) {
        if (!cancelled) setError(requestError(err))
      }
    }
    pull()
    const id = setInterval(pull, APP_LOG_POLL_MS)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [fetchJson, name])

  if (error && !lines) return <div className="text-xs text-muted-foreground">No log: {error}</div>
  return (
    <pre ref={preRef} className={cn('max-h-72 overflow-auto rounded-md bg-muted p-2 font-mono text-xs leading-relaxed', className)}>
      {lines === null ? 'Loading…' : lines.length === 0 ? 'No output yet.' : lines.map((l, i) => (
        <div key={i} className={cn(l.startsWith('[stderr]') && 'text-destructive', l.startsWith('[supervisor]') && 'text-muted-foreground')}>{l}</div>
      ))}
    </pre>
  )
}

export const Notice = ({ notice, onDismiss }: { notice: { text: string, warn?: boolean } | null, onDismiss: () => void }) => {
  if (!notice) return null
  return (
    <div className={cn('flex items-start justify-between gap-3 rounded-lg border p-3 text-sm',
      notice.warn ? 'border-amber-500/50 text-amber-700 dark:text-amber-400' : 'text-muted-foreground')}>
      <span>{notice.text}</span>
      <button className="text-xs underline-offset-2 hover:underline" onClick={onDismiss}>Dismiss</button>
    </div>
  )
}

export const DaemonNotRunning = ({ what }: { what: string }) => (
  <div className="rounded-lg border p-3 text-sm text-muted-foreground">
    The geenii daemon is not running, so {what}. Start it with <code className="font-mono">geenii daemon start</code>.
  </div>
)
