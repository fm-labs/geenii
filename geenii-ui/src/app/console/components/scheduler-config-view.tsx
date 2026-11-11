import * as React from 'react'
import {
  CalendarClockIcon, ChevronRightIcon, FileJsonIcon, LoaderIcon, PencilIcon, PlayIcon, PlusIcon, RefreshCwIcon, Trash2Icon,
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
import { processUrl } from '@/app/console/components/process-manager-view.tsx'
import SchedulerTaskDialog, { SchedulerWriteResult } from '@/app/console/components/scheduler-task-dialog.tsx'

/** Live state of a task in the running scheduler, see `Scheduler.status` in geenii/scheduler.py */
type LiveTask = {
  next_run: string | null
  last_run: string | null
  running: boolean
  last_run_id: string | null
}

/** A task entry from the scheduler config file, see `SchedulerConfig` in geenii/scheduler.py */
type SchedulerTask = {
  name: string
  interval: string
  cmd?: string[] | null
  module?: string
  params?: string[] | null
  env?: Record<string, string> | null
  working_dir?: string | null
  timeout?: number | null
  allow_overlap?: boolean
  enabled: boolean
  live: LiveTask | null
  not_in_config?: boolean
  [key: string]: unknown
}

/** Response of GET /api/v1/scheduler/config, see geenii/server/scheduler_routes.py */
type SchedulerConfigResponse = {
  path: string
  exists: boolean
  daemon: { running: boolean, config: string | null, status: string | null, error: string | null }
  tasks: SchedulerTask[]
  error: string | null
}

const fmtTime = (iso: string | null) => {
  if (!iso) return '—'
  const d = new Date(iso)
  return isNaN(d.getTime()) ? iso : d.toLocaleString()
}

const fmtRelative = (iso: string | null) => {
  if (!iso) return null
  const diff = (new Date(iso).getTime() - Date.now()) / 1000
  if (isNaN(diff)) return null
  const abs = Math.abs(diff)
  const v = abs < 60 ? `${Math.round(abs)}s` : abs < 3600 ? `${Math.round(abs / 60)}m`
    : abs < 86400 ? `${Math.round(abs / 3600)}h` : `${Math.round(abs / 86400)}d`
  return diff >= 0 ? `in ${v}` : `${v} ago`
}

const StateBadge = ({ task, daemonRunning }: { task: SchedulerTask, daemonRunning: boolean }) => {
  if (!task.enabled) return <Badge variant="outline" className="text-muted-foreground">disabled</Badge>
  if (task.live?.running) {
    return <Badge variant="secondary" className="gap-1"><LoaderIcon className="size-3 animate-spin" /> running</Badge>
  }
  if (task.live) {
    return (
      <Badge variant="secondary" className="gap-1.5">
        <span className="size-1.5 rounded-full bg-emerald-500" /> scheduled
      </Badge>
    )
  }
  // Enabled in the file but not loaded by a running scheduler: invalid entry, or not reloaded yet
  return daemonRunning
    ? <Badge variant="outline" className="text-amber-600">not loaded</Badge>
    : <Badge variant="outline">idle</Badge>
}

const Field = ({ label, children }: { label: string, children: React.ReactNode }) => (
  <div className="grid grid-cols-[8rem_minmax(0,1fr)] gap-3 py-1 text-sm">
    <dt className="text-muted-foreground">{label}</dt>
    <dd className="min-w-0 break-words font-mono text-xs">{children}</dd>
  </div>
)

const TaskRow = ({ task, daemonRunning, onEdit, onDelete, onRun }: {
  task: SchedulerTask
  daemonRunning: boolean
  onEdit: () => void
  onDelete: () => void
  onRun: () => Promise<void>
}) => {
  const [starting, setStarting] = React.useState(false)
  // Only tasks loaded in the running scheduler can run; a running task again only with allow_overlap
  const runBlocked = !task.live
    ? (daemonRunning ? 'The running scheduler has not loaded this task (disabled or invalid)' : 'The daemon is not running')
    : task.live.running && !task.allow_overlap ? 'Already running' : null
  const run = async () => {
    setStarting(true)
    try {
      await onRun()
    } finally {
      setStarting(false)
    }
  }
  const [open, setOpen] = React.useState(false)
  const target = task.cmd?.length ? task.cmd.join(' ') : task.module || '—'
  const next = task.live?.next_run ?? null

  return (
    <Collapsible open={open} onOpenChange={setOpen} className="border-b last:border-b-0">
      <CollapsibleTrigger asChild>
        <button className={cn('grid w-full grid-cols-[1rem_minmax(0,1.2fr)_minmax(0,1fr)_minmax(0,1fr)_auto] items-center gap-3 px-2 py-2.5 text-left text-sm hover:bg-muted/50',
          !task.enabled && 'opacity-60')}>
          <ChevronRightIcon className={cn('size-4 text-muted-foreground transition-transform', open && 'rotate-90')} />
          <div className="min-w-0">
            <div className="truncate font-medium">{task.name}</div>
            <div className="truncate font-mono text-xs text-muted-foreground" title={target}>{target}</div>
          </div>
          <div className="truncate font-mono text-xs">{task.interval}</div>
          <div className="truncate text-xs text-muted-foreground" title={fmtTime(next)}>
            {next ? <>next {fmtRelative(next)}</> : '—'}
          </div>
          <StateBadge task={task} daemonRunning={daemonRunning} />
        </button>
      </CollapsibleTrigger>
      <CollapsibleContent className="px-9 pb-3">
        <dl>
          {task.cmd?.length ? <Field label="Command">{JSON.stringify(task.cmd)}</Field> : null}
          {task.module ? <Field label="Module">{task.module}</Field> : null}
          {task.params?.length ? <Field label="Params">{JSON.stringify(task.params)}</Field> : null}
          {task.working_dir ? <Field label="Working dir">{task.working_dir}</Field> : null}
          {task.env && Object.keys(task.env).length > 0 && (
            <Field label="Env">{Object.entries(task.env).map(([k, v]) => <div key={k}>{k}={v}</div>)}</Field>
          )}
          <Field label="Timeout">{task.timeout ? `${task.timeout}s` : 'no limit'}</Field>
          <Field label="Allow overlap">{task.allow_overlap ? 'yes' : 'no'}</Field>
          {task.live && (
            <>
              <Field label="Next run">{fmtTime(task.live.next_run)}</Field>
              <Field label="Last run">{fmtTime(task.live.last_run)}</Field>
              {task.live.last_run_id && (
                <Field label="Last run ID">
                  <a className="underline-offset-2 hover:underline" href={processUrl(task.live.last_run_id)}>{task.live.last_run_id}</a>
                </Field>
              )}
            </>
          )}
          {task.not_in_config && (
            <div className="pt-1 text-xs text-amber-600">
              Running in the daemon but not in the config file (added at runtime, or the file changed since the last reload).
            </div>
          )}
        </dl>
        <div className="flex gap-2 pt-2">
          <span title={runBlocked ?? 'Start a run now, outside the schedule'}>
            <Button size="sm" variant="outline" onClick={run} disabled={!!runBlocked || starting}>
              {starting ? <LoaderIcon className="animate-spin" /> : <PlayIcon />} Run now
            </Button>
          </span>
          {!task.not_in_config && (<>
            <Button size="sm" variant="outline" onClick={onEdit}><PencilIcon /> Edit</Button>
            <Button size="sm" variant="ghost" className="text-destructive hover:text-destructive" onClick={onDelete}>
              <Trash2Icon /> Delete
            </Button>
          </>)}
        </div>
      </CollapsibleContent>
    </Collapsible>
  )
}

const SchedulerConfigView = () => {
  const { fetchJson } = useApi()
  const [data, setData] = React.useState<SchedulerConfigResponse | null>(null)
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)
  // null: closed; 'new': add dialog; a task: edit dialog
  const [editing, setEditing] = React.useState<SchedulerTask | 'new' | null>(null)
  const [deleting, setDeleting] = React.useState<SchedulerTask | null>(null)
  const [notice, setNotice] = React.useState<{ text: string, warn?: boolean } | null>(null)

  const load = React.useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setData(await fetchJson('/api/v1/scheduler/config'))
    } catch (err) {
      console.error('Error fetching scheduler config:', err)
      setError(err?.message || 'Unknown error')
    } finally {
      setLoading(false)
    }
  }, [fetchJson])

  React.useEffect(() => {
    load()
  }, [load])

  const onWritten = (action: string, result: SchedulerWriteResult) => {
    const { reload } = result
    if (reload.error) {
      setNotice({ text: `${action}, but the daemon could not reload the config: ${reload.error}`, warn: true })
    } else if (reload.reloaded) {
      setNotice({ text: `${action}; the running daemon reloaded the config.` })
    } else {
      setNotice({ text: `${action}. It takes effect when the daemon starts with this config.` })
    }
    load()
  }

  const runTask = async (name: string) => {
    try {
      await fetchJson(`/api/v1/scheduler/tasks/${encodeURIComponent(name)}/run`, { method: 'POST' })
      setNotice({ text: `Started task "${name}".` })
    } catch (err) {
      setNotice({ text: `Could not start task "${name}": ${err?.message || 'Unknown error'}`, warn: true })
    }
    // Show the run as running, then (for short runs) as finished
    load()
    setTimeout(load, 3000)
  }

  const confirmDelete = async () => {
    if (!deleting) return
    const name = deleting.name
    setDeleting(null)
    try {
      const result = await fetchJson(`/api/v1/scheduler/tasks/${encodeURIComponent(name)}`, { method: 'DELETE' })
      onWritten(`Deleted task "${name}"`, result)
    } catch (err) {
      setNotice({ text: `Could not delete task "${name}": ${err?.message || 'Unknown error'}`, warn: true })
    }
  }

  const daemon = data?.daemon
  const enabled = data?.tasks.filter((t) => t.enabled).length ?? 0

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-end gap-2">
        <Button size="sm" variant="ghost" onClick={load} disabled={loading}>
          <RefreshCwIcon className={loading ? 'animate-spin' : ''} /> Refresh
        </Button>
        <Button size="sm" onClick={() => setEditing('new')} disabled={!data || !!data.error}>
          <PlusIcon /> Add task
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
          Failed to load scheduler config: {error}
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
                {daemon?.running && <Badge variant="outline">scheduler {daemon.status}</Badge>}
              </div>
              {!daemon?.running && (
                <div className="text-muted-foreground">
                  Showing the config file only. Start the daemon with <code className="font-mono">geenii daemon start</code> to see next and last runs.
                </div>
              )}
              {daemon?.error && <div className="text-destructive">Daemon error: {daemon.error}</div>}
              {data.error && <div className="text-destructive">{data.error}</div>}
            </CardContent>
          </Card>

          <Card className="gap-3">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <CalendarClockIcon size={16} className="text-muted-foreground" /> Tasks
              </CardTitle>
              <CardDescription>{data.tasks.length} task(s), {enabled} enabled</CardDescription>
            </CardHeader>
            <CardContent>
              {data.tasks.length === 0 ? (
                <div className="text-sm text-muted-foreground">
                  {data.exists ? 'The config file has no tasks yet.' : 'No scheduler config file yet; adding a task creates it.'}
                </div>
              ) : (
                <div className="rounded-md border">
                  {data.tasks.map((t, i) => (
                    <TaskRow key={`${t.name}-${i}`} task={t} daemonRunning={!!daemon?.running}
                             onEdit={() => setEditing(t)} onDelete={() => setDeleting(t)}
                             onRun={() => runTask(t.name)} />
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

      <SchedulerTaskDialog
        open={editing !== null}
        onOpenChange={(open) => !open && setEditing(null)}
        task={editing === 'new' ? null : editing}
        onSaved={(result) => onWritten(editing === 'new' ? 'Added task' : 'Saved task', result)}
      />

      <AlertDialog open={deleting !== null} onOpenChange={(open) => !open && setDeleting(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete task &quot;{deleting?.name}&quot;?</AlertDialogTitle>
            <AlertDialogDescription>
              It is removed from the scheduler config. A run already in progress is allowed to finish.
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

export default SchedulerConfigView
