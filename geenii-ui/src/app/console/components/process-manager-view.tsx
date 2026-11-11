import * as React from 'react'
import { BrushCleaningIcon, CpuIcon, LoaderIcon, OctagonXIcon, PlusIcon, RefreshCwIcon, SquareIcon, Trash2Icon, XIcon } from 'lucide-react'
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog.tsx'
import { Badge } from '@/components/ui/badge.tsx'
import { Button } from '@/components/ui/button.tsx'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.tsx'
import { Label } from '@/components/ui/label.tsx'
import { Skeleton } from '@/components/ui/skeleton.tsx'
import { Switch } from '@/components/ui/switch.tsx'
import { useApi } from '@/context/api-context.tsx'
import { useRoute } from '@/app-router.tsx'
import { ApiError, readProblem } from '@/api/api-error.ts'
import { cn } from 'cn'
import ProcessOutput from '@/app/console/components/process-output.tsx'
import ProcessStartDialog from '@/app/console/components/process-start-dialog.tsx'

const POLL_MS = 2000
const ROUTE = '/console/system/processes'

export type ProcessState = 'pending' | 'running' | 'completed' | 'failed' | 'killed' | 'orphaned'

/** A background process, see `ProcessInfo.to_dict` in geenii/pm/process_manager.py */
export type ProcessInfo = {
  pid: string
  system_pid: number | null
  cmd: string | string[]
  shell: boolean
  state: ProcessState
  cwd: string | null
  env_keys: string[]
  started_at: number | null
  finished_at: number | null
  exit_code: number | null
  error: string | null
  stdout_path: string | null
  stderr_path: string | null
}

type GcResult = { removed: string[], count: number, dry_run: boolean }

const GC_AGES: [string, number][] = [
  ['any age', 0],
  ['1 hour', 3600],
  ['1 day', 86400],
  ['7 days', 7 * 86400],
  ['30 days', 30 * 86400],
]

export const processUrl = (pid: string) => `#${ROUTE}?pid=${encodeURIComponent(pid)}`

export const isActive = (p: ProcessInfo | null | undefined) => !!p && (p.state === 'running' || p.state === 'pending')

const fmtCmd = (cmd: string | string[]) =>
  Array.isArray(cmd) ? cmd.map((a) => (/[\s"'\\$]/.test(a) ? JSON.stringify(a) : a)).join(' ') : cmd

const fmtTime = (t: number | null) => (t ? new Date(t * 1000).toLocaleString() : '—')

/** Time of day for today's processes, the date for older ones */
const fmtShort = (t: number | null) => {
  if (!t) return '—'
  const d = new Date(t * 1000)
  return d.toDateString() === new Date().toDateString()
    ? d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : d.toLocaleDateString([], { month: 'short', day: 'numeric' })
}

const fmtDuration = (p: ProcessInfo) => {
  if (!p.started_at) return '—'
  const s = Math.max(0, (p.finished_at || Date.now() / 1000) - p.started_at)
  if (s < 60) return `${s.toFixed(1)}s`
  if (s < 3600) return `${Math.floor(s / 60)}m ${Math.round(s % 60)}s`
  return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`
}

const STATE_STYLE: Record<ProcessState, string> = {
  pending: 'text-muted-foreground',
  running: 'text-sky-600 dark:text-sky-400',
  completed: 'text-emerald-600 dark:text-emerald-400',
  failed: 'text-destructive',
  killed: 'text-amber-600 dark:text-amber-400',
  orphaned: 'text-amber-600 dark:text-amber-400',
}

export const ProcessStateBadge = ({ p }: { p: ProcessInfo }) => (
  <Badge variant="outline" className={cn('gap-1', STATE_STYLE[p.state])}>
    {isActive(p) && <LoaderIcon className="size-3 animate-spin" />}
    {p.state}
    {p.exit_code != null && p.state !== 'completed' && <span className="font-mono">({p.exit_code})</span>}
  </Badge>
)

const Field = ({ label, children }: { label: string, children: React.ReactNode }) => (
  <div className="grid grid-cols-[7rem_minmax(0,1fr)] gap-3 py-1 text-sm">
    <dt className="text-muted-foreground">{label}</dt>
    <dd className="min-w-0 break-words">{children}</dd>
  </div>
)

/** The selected process from the route, e.g. #/console/system/processes?pid=abc */
const useSelectedPid = (): [string | null, (pid: string | null) => void] => {
  const { location } = useRoute()
  const pid = new URLSearchParams(location.split('?')[1] || '').get('pid')
  const select = React.useCallback((pid: string | null) => {
    window.location.hash = pid ? processUrl(pid) : `#${ROUTE}`
  }, [])
  return [pid, select]
}

const ProcessManagerView = () => {
  const { fetch, fetchJson } = useApi()
  const [selected, select] = useSelectedPid()
  const [showFinished, setShowFinished] = React.useState(true)
  const [processes, setProcesses] = React.useState<ProcessInfo[] | null>(null)
  const [current, setCurrent] = React.useState<ProcessInfo | null>(null)
  const [error, setError] = React.useState<{ text: string, offline?: boolean } | null>(null)
  const [notice, setNotice] = React.useState<{ text: string, warn?: boolean } | null>(null)
  const [loading, setLoading] = React.useState(false)
  const [tick, setTick] = React.useState(0)
  const [starting, setStarting] = React.useState(false)
  const [busy, setBusy] = React.useState<string | null>(null)
  const [confirmCleanup, setConfirmCleanup] = React.useState(false)
  const [gcAge, setGcAge] = React.useState(7 * 86400)
  const [gcPreview, setGcPreview] = React.useState<GcResult | null>(null)

  const load = React.useCallback(async () => {
    setLoading(true)
    try {
      const list: ProcessInfo[] = await fetchJson(`/api/v1/pm/processes?include_finished=${showFinished}`)
      // Newest first
      list.sort((a, b) => (b.started_at ?? 0) - (a.started_at ?? 0))
      setProcesses(list)
      setError(null)
      if (selected) {
        try {
          setCurrent(await fetchJson(`/api/v1/pm/processes/${encodeURIComponent(selected)}`))
        } catch (err) {
          if (err instanceof ApiError && err.status === 404) setCurrent(null)
          else throw err
        }
      }
    } catch (err) {
      const offline = err instanceof ApiError && err.status === 503
      setError({ text: err?.message || 'Unknown error', offline })
    } finally {
      setLoading(false)
      setTick((t) => t + 1)
    }
  }, [fetchJson, showFinished, selected])

  // Show the list entry right away when the selection changes, then poll
  React.useEffect(() => {
    setCurrent(processes?.find((p) => p.pid === selected) ?? null)
    // only on selection changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected])

  React.useEffect(() => {
    load()
    const id = setInterval(() => {
      if (document.visibilityState === 'visible') load()
    }, POLL_MS)
    return () => clearInterval(id)
  }, [load])

  const action = async (label: string, fn: () => Promise<unknown>) => {
    setBusy(label)
    try {
      await fn()
      setNotice(null)
    } catch (err) {
      setNotice({ text: err?.message || 'Unknown error', warn: true })
    } finally {
      setBusy(null)
      load()
    }
  }

  const kill = (force: boolean) => action(force ? 'force' : 'kill', () =>
    fetchJson(`/api/v1/pm/processes/${encodeURIComponent(selected!)}/kill${force ? '?force=true' : ''}`, { method: 'POST' }))

  const cleanup = () => {
    const pid = selected!
    setConfirmCleanup(false)
    action('cleanup', async () => {
      // 204 without a body, so not fetchJson
      const res = await fetch(`/api/v1/pm/processes/${encodeURIComponent(pid)}`, { method: 'DELETE' })
      if (!res.ok) throw new ApiError(res.status, await readProblem(res))
      select(null)
      setNotice({ text: `Deleted the logs of process ${pid}.` })
    })
  }

  const gcDryRun = () => action('gc', async () => {
    const preview: GcResult = await fetchJson(`/api/v1/pm/gc?max_age=${gcAge}&dry_run=true`, { method: 'POST' })
    if (!preview.count) setNotice({ text: 'Nothing to clean up.' })
    else setGcPreview(preview)
  })

  const gcRun = () => {
    setGcPreview(null)
    action('gc', async () => {
      const res: GcResult = await fetchJson(`/api/v1/pm/gc?max_age=${gcAge}`, { method: 'POST' })
      setNotice({ text: `Deleted the logs of ${res.count} process(es).` })
      if (selected && res.removed.includes(selected)) select(null)
    })
  }

  const gcAgeLabel = GC_AGES.find(([, s]) => s === gcAge)?.[0]
  const active = isActive(current)
  const running = processes?.filter(isActive).length ?? 0

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-end gap-2">
        <div className="mr-auto flex items-center gap-2">
          <Switch id="pm-finished" checked={showFinished} onCheckedChange={setShowFinished} />
          <Label htmlFor="pm-finished" className="text-sm font-normal">Show finished</Label>
        </div>
        <Button size="sm" variant="ghost" onClick={load} disabled={loading}>
          <RefreshCwIcon className={loading ? 'animate-spin' : ''} /> Refresh
        </Button>
        <Button size="sm" onClick={() => setStarting(true)} disabled={!!error?.offline}>
          <PlusIcon /> Start process
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
          {error.offline
            ? <>The geenii daemon is not running. Start it with <code className="font-mono">geenii daemon start</code>.</>
            : <>Failed to load processes: {error.text}</>}
        </div>
      )}

      {!processes && !error && <Skeleton className="h-64 rounded-xl" />}

      {processes && (
        <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
          <Card className="gap-3">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <CpuIcon size={16} className="text-muted-foreground" /> Processes
              </CardTitle>
              <CardDescription>
                {processes.length} process(es), {running} running
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              {processes.length === 0 ? (
                <div className="text-sm text-muted-foreground">
                  {showFinished ? 'No processes yet.' : 'No running processes.'}
                </div>
              ) : (
                <div className="max-h-[32rem] overflow-auto rounded-md border">
                  {processes.map((p) => (
                    <button key={p.pid} onClick={() => select(p.pid)}
                            className={cn('grid w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-0.5 border-b px-3 py-2 text-left last:border-b-0 hover:bg-muted/50',
                              p.pid === selected && 'bg-muted')}>
                      <span className="truncate font-mono text-xs font-medium" title={p.pid}>{p.pid}</span>
                      <ProcessStateBadge p={p} />
                      <span className="truncate font-mono text-xs text-muted-foreground" title={fmtCmd(p.cmd)}>{fmtCmd(p.cmd)}</span>
                      <span className="text-right text-xs text-muted-foreground" title={fmtTime(p.started_at)}>{fmtShort(p.started_at)}</span>
                    </button>
                  ))}
                </div>
              )}

              <div className="flex flex-wrap items-center gap-2 border-t pt-3 text-sm">
                <span className="text-muted-foreground">Delete logs of finished processes older than</span>
                <select value={gcAge} onChange={(e) => setGcAge(Number(e.target.value))}
                        className="h-8 rounded-md border bg-transparent px-2 text-sm">
                  {GC_AGES.map(([label, s]) => <option key={s} value={s}>{label}</option>)}
                </select>
                <Button size="sm" variant="outline" onClick={gcDryRun} disabled={busy === 'gc' || !!error?.offline}>
                  {busy === 'gc' ? <LoaderIcon className="animate-spin" /> : <BrushCleaningIcon />} Clean up
                </Button>
              </div>
            </CardContent>
          </Card>

          <Card className="gap-3">
            {!selected ? (
              <CardContent className="py-12 text-center text-sm text-muted-foreground">
                Select a process to see its details and output.
              </CardContent>
            ) : !current ? (
              <CardContent className="flex items-center justify-between gap-3 text-sm text-muted-foreground">
                <span>{loading ? 'Loading…' : <>Process <span className="font-mono">{selected}</span> not found (its logs may have been deleted).</>}</span>
                <Button size="sm" variant="ghost" onClick={() => select(null)}><XIcon /></Button>
              </CardContent>
            ) : (<>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <span className="truncate font-mono">{current.pid}</span>
                  <ProcessStateBadge p={current} />
                  <Button size="sm" variant="ghost" className="ml-auto" onClick={() => select(null)} title="Close"><XIcon /></Button>
                </CardTitle>
                <CardDescription className="break-all font-mono text-xs">{fmtCmd(current.cmd)}</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-4">
                <dl className="grid gap-x-6 sm:grid-cols-2">
                  <Field label="Started">{fmtTime(current.started_at)}</Field>
                  <Field label="Finished">{fmtTime(current.finished_at)}</Field>
                  <Field label="Duration">{fmtDuration(current)}</Field>
                  <Field label="Exit code"><span className="font-mono">{current.exit_code ?? '—'}</span></Field>
                  <Field label="System PID"><span className="font-mono">{current.system_pid ?? '—'}</span></Field>
                  <Field label="Shell">{current.shell ? 'yes' : 'no'}</Field>
                  <Field label="Working dir"><span className="font-mono text-xs">{current.cwd || '—'}</span></Field>
                  <Field label="Env keys"><span className="font-mono text-xs">{current.env_keys.join(', ') || '—'}</span></Field>
                </dl>
                {current.error && <div className="text-sm text-destructive">{current.error}</div>}

                <div className="flex flex-wrap gap-2">
                  <Button size="sm" variant="outline" onClick={() => kill(false)} disabled={!active || !!busy}
                          title="Send SIGTERM">
                    {busy === 'kill' ? <LoaderIcon className="animate-spin" /> : <SquareIcon />} Stop
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => kill(true)} disabled={!active || !!busy}
                          title="Send SIGKILL">
                    {busy === 'force' ? <LoaderIcon className="animate-spin" /> : <OctagonXIcon />} Force kill
                  </Button>
                  <Button size="sm" variant="ghost" className="text-destructive hover:text-destructive"
                          onClick={() => setConfirmCleanup(true)} disabled={active || !!busy}
                          title={active ? 'Stop the process first' : 'Delete its logs'}>
                    <Trash2Icon /> Delete logs
                  </Button>
                </div>

                <ProcessOutput pid={current.pid} active={active} tick={tick} />
              </CardContent>
            </>)}
          </Card>
        </div>
      )}

      <ProcessStartDialog open={starting} onOpenChange={setStarting}
                          onStarted={(p) => { select(p.pid); load() }} />

      <AlertDialog open={confirmCleanup} onOpenChange={setConfirmCleanup}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete the logs of process {selected}?</AlertDialogTitle>
            <AlertDialogDescription>Its output and state are removed from disk.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={cleanup}>Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={gcPreview !== null} onOpenChange={(open) => !open && setGcPreview(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete the logs of {gcPreview?.count} process(es)?</AlertDialogTitle>
            <AlertDialogDescription>
              Completed, failed and killed processes{gcAge ? ` that finished more than ${gcAgeLabel} ago` : ''}.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="max-h-48 overflow-auto rounded-md border p-2 font-mono text-xs">
            {gcPreview?.removed.map((pid) => <div key={pid}>{pid}</div>)}
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={gcRun}>Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

export default ProcessManagerView
