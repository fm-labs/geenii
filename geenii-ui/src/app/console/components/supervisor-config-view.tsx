import * as React from 'react'
import {
  ChevronRightIcon, FileJsonIcon, LoaderIcon, PencilIcon, PlayIcon, PlusIcon, RefreshCwIcon, RotateCwIcon,
  ServerCogIcon, SquareIcon, Trash2Icon,
} from 'lucide-react'
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog.tsx'
import { Badge } from '@/components/ui/badge.tsx'
import { Button } from '@/components/ui/button.tsx'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.tsx'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible.tsx'
import { Skeleton } from '@/components/ui/skeleton.tsx'
import JsonView from '@/components/json-view.tsx'
import { useApi } from '@/context/api-context.tsx'
import { cn } from 'cn'
import { requestError } from '@/app/console/components/scheduler-task-dialog.tsx'
import SupervisorServiceDialog, { SupervisorWriteResult } from '@/app/console/components/supervisor-service-dialog.tsx'

/** Refresh interval of the list while the daemon is running */
const POLL_MS = 5000
/** Refresh interval of an open log */
const LOG_POLL_MS = 2000

/** Supervisor state of a service, see `_live_state` in geenii/server/supervisor_routes.py */
type LiveService = {
  state: 'running' | 'restarting' | 'stopped'
  source: 'config' | 'api'
  pid: number | null
  uptime_s: number | null
  backoff_s: number | null
  last_exit: { returncode: number, exited_at: number } | null
  restart: boolean
}

/** A service entry from the services config file, see `ServiceConfig` in geenii/supervisor.py */
type Service = {
  name: string
  cmd: string[]
  restart: boolean
  env?: Record<string, string> | null
  cwd?: string | null
  capture_output?: boolean
  enabled: boolean
  live: LiveService | null
  not_in_config?: boolean
  [key: string]: unknown
}

/** Response of GET /api/v1/supervisor/config, see geenii/server/supervisor_routes.py */
type SupervisorConfigResponse = {
  path: string
  exists: boolean
  daemon: { running: boolean, config: string | null, error: string | null }
  services: Service[]
  error: string | null
}

type Action = 'start' | 'stop' | 'restart'

const fmtUptime = (s: number | null) => {
  if (s == null) return '—'
  if (s < 60) return `${Math.round(s)}s`
  if (s < 3600) return `${Math.floor(s / 60)}m ${Math.round(s % 60)}s`
  if (s < 86400) return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`
  return `${Math.floor(s / 86400)}d ${Math.floor((s % 86400) / 3600)}h`
}

const StateBadge = ({ service, daemonRunning }: { service: Service, daemonRunning: boolean }) => {
  const live = service.live
  if (!service.enabled) return <Badge variant="outline" className="text-muted-foreground">disabled</Badge>
  if (live?.state === 'running') {
    return (
      <Badge variant="secondary" className="gap-1.5">
        <span className="size-1.5 rounded-full bg-emerald-500" /> running
      </Badge>
    )
  }
  if (live?.state === 'restarting') {
    return <Badge variant="outline" className="gap-1 text-amber-600"><LoaderIcon className="size-3 animate-spin" /> restarting</Badge>
  }
  if (live?.state === 'stopped') return <Badge variant="outline">stopped</Badge>
  // Enabled in the file but not supervised: stopped for good, invalid entry, or not applied yet
  return daemonRunning
    ? <Badge variant="outline" className="text-muted-foreground">not running</Badge>
    : <Badge variant="outline">idle</Badge>
}

const Field = ({ label, children }: { label: string, children: React.ReactNode }) => (
  <div className="grid grid-cols-[8rem_minmax(0,1fr)] gap-3 py-1 text-sm">
    <dt className="text-muted-foreground">{label}</dt>
    <dd className="min-w-0 break-words font-mono text-xs">{children}</dd>
  </div>
)

/** Recent output of a service, re-read while shown */
const ServiceLog = ({ name }: { name: string }) => {
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
        const res = await fetchJson(`/api/v1/supervisor/services/${encodeURIComponent(name)}/logs?tail=500`)
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
    const id = setInterval(pull, LOG_POLL_MS)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [fetchJson, name])

  if (error && !lines) return <div className="text-xs text-muted-foreground">No log: {error}</div>
  return (
    <pre ref={preRef} className="max-h-72 overflow-auto rounded-md bg-muted p-2 font-mono text-xs leading-relaxed">
      {lines === null ? 'Loading…' : lines.length === 0 ? 'No output yet.' : lines.map((l, i) => (
        <div key={i} className={cn(l.startsWith('[stderr]') && 'text-destructive', l.startsWith('[supervisor]') && 'text-muted-foreground')}>{l}</div>
      ))}
    </pre>
  )
}

const ServiceRow = ({ service, daemonRunning, onEdit, onDelete, onAction }: {
  service: Service
  daemonRunning: boolean
  onEdit: () => void
  onDelete: () => void
  onAction: (action: Action) => Promise<void>
}) => {
  const [open, setOpen] = React.useState(false)
  const [busy, setBusy] = React.useState<Action | null>(null)
  const live = service.live
  const target = service.cmd?.join(' ') || '—'

  const act = async (action: Action) => {
    setBusy(action)
    try {
      await onAction(action)
    } finally {
      setBusy(null)
    }
  }

  // A supervised service can be stopped/restarted; any other enabled one (config or kept) can be started
  const notRunningReason = !daemonRunning ? 'The daemon is not running' : null
  const canStart = daemonRunning && service.enabled && live?.state !== 'running' && live?.state !== 'restarting'
  const canStop = daemonRunning && !!live && live.state !== 'stopped'
  const canRestart = daemonRunning && !!live

  return (
    <Collapsible open={open} onOpenChange={setOpen} className="border-b last:border-b-0">
      <CollapsibleTrigger asChild>
        <button className={cn('grid w-full grid-cols-[1rem_minmax(0,1.6fr)_minmax(0,0.8fr)_minmax(0,0.6fr)_auto] items-center gap-3 px-2 py-2.5 text-left text-sm hover:bg-muted/50',
          !service.enabled && 'opacity-60')}>
          <ChevronRightIcon className={cn('size-4 text-muted-foreground transition-transform', open && 'rotate-90')} />
          <div className="min-w-0">
            <div className="truncate font-medium">{service.name}</div>
            <div className="truncate font-mono text-xs text-muted-foreground" title={target}>{target}</div>
          </div>
          <div className="truncate text-xs text-muted-foreground">
            {live?.state === 'running' ? <>up {fmtUptime(live.uptime_s)}</> : service.restart ? 'keep running' : 'run once'}
          </div>
          <div className="truncate font-mono text-xs text-muted-foreground">{live?.pid ? `pid ${live.pid}` : ''}</div>
          <StateBadge service={service} daemonRunning={daemonRunning} />
        </button>
      </CollapsibleTrigger>
      <CollapsibleContent className="px-9 pb-3">
        <dl>
          <Field label="Command">{JSON.stringify(service.cmd)}</Field>
          {service.cwd ? <Field label="Working dir">{service.cwd}</Field> : null}
          {service.env && Object.keys(service.env).length > 0 && (
            <Field label="Env">{Object.entries(service.env).map(([k, v]) => <div key={k}>{k}={v}</div>)}</Field>
          )}
          <Field label="Restart">{service.restart ? 'when it exits (with backoff)' : 'no, run once'}</Field>
          {service.capture_output === false && <Field label="Output">not captured</Field>}
          {live && (
            <>
              {live.pid && <Field label="PID">{live.pid}</Field>}
              {live.state === 'running' && <Field label="Uptime">{fmtUptime(live.uptime_s)}</Field>}
              {live.last_exit && (
                <Field label="Last exit">
                  rc={live.last_exit.returncode} at {new Date(live.last_exit.exited_at * 1000).toLocaleString()}
                </Field>
              )}
            </>
          )}
          {service.not_in_config && (
            <div className="pt-1 text-xs text-amber-600">
              Supervised by the daemon but not in the config file (started with <code>geenii supervisor start</code>); it is gone when the daemon stops.
            </div>
          )}
        </dl>
        <div className="flex flex-wrap gap-2 pt-2">
          <span title={notRunningReason ?? (!service.enabled ? 'Disabled' : 'Start the service')}>
            <Button size="sm" variant="outline" onClick={() => act('start')} disabled={!canStart || !!busy}>
              {busy === 'start' ? <LoaderIcon className="animate-spin" /> : <PlayIcon />} Start
            </Button>
          </span>
          <span title={notRunningReason ?? 'Stop the service; it stays stopped until started again or the daemon restarts'}>
            <Button size="sm" variant="outline" onClick={() => act('stop')} disabled={!canStop || !!busy}>
              {busy === 'stop' ? <LoaderIcon className="animate-spin" /> : <SquareIcon />} Stop
            </Button>
          </span>
          <span title={notRunningReason ?? 'Restart now (also resets the restart backoff)'}>
            <Button size="sm" variant="outline" onClick={() => act('restart')} disabled={!canRestart || !!busy}>
              {busy === 'restart' ? <LoaderIcon className="animate-spin" /> : <RotateCwIcon />} Restart
            </Button>
          </span>
          {!service.not_in_config && (<>
            <Button size="sm" variant="outline" onClick={onEdit}><PencilIcon /> Edit</Button>
            <Button size="sm" variant="ghost" className="text-destructive hover:text-destructive" onClick={onDelete}>
              <Trash2Icon /> Delete
            </Button>
          </>)}
        </div>
        {open && daemonRunning && (
          <div className="pt-3">
            <div className="pb-1 text-xs font-medium text-muted-foreground">Log</div>
            <ServiceLog name={service.name} />
          </div>
        )}
      </CollapsibleContent>
    </Collapsible>
  )
}

const SupervisorConfigView = () => {
  const { fetchJson } = useApi()
  const [data, setData] = React.useState<SupervisorConfigResponse | null>(null)
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)
  // null: closed; 'new': add dialog; a service: edit dialog
  const [editing, setEditing] = React.useState<Service | 'new' | null>(null)
  const [deleting, setDeleting] = React.useState<Service | null>(null)
  const [notice, setNotice] = React.useState<{ text: string, warn?: boolean } | null>(null)

  /** Load the config; `quiet` for background polls (no loading state, errors kept from the last load) */
  const load = React.useCallback(async (quiet = false) => {
    if (!quiet) {
      setLoading(true)
      setError(null)
    }
    try {
      setData(await fetchJson('/api/v1/supervisor/config'))
      if (quiet) setError(null)
    } catch (err) {
      console.error('Error fetching supervisor config:', err)
      if (!quiet) setError(err?.message || 'Unknown error')
    } finally {
      if (!quiet) setLoading(false)
    }
  }, [fetchJson])

  React.useEffect(() => {
    load()
  }, [load])

  // Keep states and uptimes current while the daemon runs
  const daemonRunning = !!data?.daemon.running
  React.useEffect(() => {
    if (!daemonRunning) return
    const id = setInterval(() => load(true), POLL_MS)
    return () => clearInterval(id)
  }, [daemonRunning, load])

  const onWritten = (what: string, result: SupervisorWriteResult) => {
    const { reload } = result
    if (reload.error) {
      setNotice({ text: `${what}, but the daemon could not apply the config: ${reload.error}`, warn: true })
    } else if (reload.reloaded) {
      const changes = Object.entries(reload.changes ?? {}).filter(([, v]) => v.length)
        .map(([k, v]) => `${k} ${v.join(', ')}`).join('; ')
      setNotice({ text: `${what}; the running daemon applied the config${changes ? ` (${changes})` : ''}.` })
    } else {
      setNotice({ text: `${what}. It takes effect when the daemon starts with this config.` })
    }
    load()
  }

  const runAction = async (name: string, action: Action) => {
    try {
      await fetchJson(`/api/v1/supervisor/services/${encodeURIComponent(name)}/${action}`, { method: 'POST' })
      setNotice({ text: `${action === 'stop' ? 'Stopped' : action === 'start' ? 'Started' : 'Restarted'} "${name}".` })
    } catch (err) {
      setNotice({ text: `Could not ${action} "${name}": ${requestError(err)}`, warn: true })
    }
    // Show the new state, then (after a spawn or a quick crash) the settled one
    await load(true)
    setTimeout(() => load(true), 1500)
  }

  const confirmDelete = async () => {
    if (!deleting) return
    const name = deleting.name
    setDeleting(null)
    try {
      const result = await fetchJson(`/api/v1/supervisor/services/${encodeURIComponent(name)}`, { method: 'DELETE' })
      onWritten(`Deleted service "${name}"`, result)
    } catch (err) {
      setNotice({ text: `Could not delete service "${name}": ${requestError(err)}`, warn: true })
    }
  }

  const daemon = data?.daemon
  const running = data?.services.filter((s) => s.live?.state === 'running').length ?? 0

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-end gap-2">
        <Button size="sm" variant="ghost" onClick={() => load()} disabled={loading}>
          <RefreshCwIcon className={loading ? 'animate-spin' : ''} /> Refresh
        </Button>
        <Button size="sm" onClick={() => setEditing('new')} disabled={!data || !!data.error}>
          <PlusIcon /> Add service
        </Button>
      </div>

      {notice && (
        <div className={cn('flex items-start justify-between gap-3 rounded-lg border p-3 text-sm',
          notice.warn ? 'border-amber-500/50 text-amber-700 dark:text-amber-400' : 'text-muted-foreground')}>
          <span>{notice.text}</span>
          <button className="text-xs underline-offset-2 hover:underline" onClick={() => setNotice(null)}>Dismiss</button>
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-destructive/50 p-4 text-sm text-destructive">
          Failed to load services: {error}
        </div>
      )}

      {!data && loading && <Skeleton className="h-64 rounded-xl" />}

      {data && (
        <div className={cn('flex flex-col gap-4 transition-opacity', loading && 'opacity-60')}>
          <Card className="gap-3">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <FileJsonIcon size={16} className="text-muted-foreground" /> Config file
              </CardTitle>
              <CardDescription className="flex flex-wrap items-center gap-2">
                <span className="break-all font-mono text-xs">{data.path}</span>
                {!data.exists && <Badge variant="outline">not found</Badge>}
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-2 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant={daemon?.running ? 'secondary' : 'outline'} className="gap-1.5">
                  <span className={cn('size-1.5 rounded-full', daemon?.running ? 'bg-emerald-500' : 'bg-destructive')} />
                  daemon {daemon?.running ? 'running' : 'not running'}
                </Badge>
              </div>
              {!daemon?.running && (
                <div className="text-muted-foreground">
                  Showing the config file only. Start the daemon with <code className="font-mono">geenii daemon start</code> to run the services.
                </div>
              )}
              {daemon?.error && <div className="text-destructive">Daemon error: {daemon.error}</div>}
              {data.error && <div className="text-destructive">{data.error}</div>}
            </CardContent>
          </Card>

          <Card className="gap-3">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <ServerCogIcon size={16} className="text-muted-foreground" /> Services
              </CardTitle>
              <CardDescription>
                {data.services.length} service(s){daemon?.running ? `, ${running} running` : ''}.
                Long-running processes the daemon keeps alive and restarts when they exit.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {data.services.length === 0 ? (
                <div className="text-sm text-muted-foreground">
                  {data.exists ? 'The config file has no services yet.' : 'No services config file yet; adding a service creates it.'}
                </div>
              ) : (
                <div className="rounded-md border">
                  {data.services.map((s, i) => (
                    <ServiceRow key={`${s.name}-${i}`} service={s} daemonRunning={!!daemon?.running}
                                onEdit={() => setEditing(s)} onDelete={() => setDeleting(s)}
                                onAction={(action) => runAction(s.name, action)} />
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="gap-3">
            <CardHeader>
              <CardTitle className="text-base">Raw data</CardTitle>
            </CardHeader>
            <CardContent>
              <Collapsible>
                <CollapsibleTrigger asChild>
                  <Button variant="ghost" size="sm" className="-ml-2 text-muted-foreground">
                    <ChevronRightIcon /> Show JSON
                  </Button>
                </CollapsibleTrigger>
                <CollapsibleContent className="pt-2"><JsonView src={data} /></CollapsibleContent>
              </Collapsible>
            </CardContent>
          </Card>
        </div>
      )}

      <SupervisorServiceDialog
        open={editing !== null}
        onOpenChange={(open) => !open && setEditing(null)}
        service={editing === 'new' ? null : editing}
        onSaved={(result) => onWritten(editing === 'new' ? 'Added service' : 'Saved service', result)}
      />

      <AlertDialog open={deleting !== null} onOpenChange={(open) => !open && setDeleting(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete service &quot;{deleting?.name}&quot;?</AlertDialogTitle>
            <AlertDialogDescription>
              It is removed from the services config, and a running daemon that uses this config stops it.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDelete}>Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

export default SupervisorConfigView
