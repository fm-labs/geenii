import * as React from 'react'
import { Button } from '@/components/ui/button.tsx'
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from '@/components/ui/dialog.tsx'
import { Input } from '@/components/ui/input.tsx'
import { Label } from '@/components/ui/label.tsx'
import { Switch } from '@/components/ui/switch.tsx'
import { Textarea } from '@/components/ui/textarea.tsx'
import { useApi } from '@/context/api-context.tsx'
import { cn } from 'cn'

/** Body of POST /api/v1/scheduler/tasks and PUT /api/v1/scheduler/tasks/{name}, see TaskInput in scheduler_routes.py */
export type SchedulerTaskInput = {
  name: string
  interval: string
  cmd?: string[] | null
  module?: string | null
  params?: string[] | null
  env?: Record<string, string> | null
  working_dir?: string | null
  timeout?: number | null
  allow_overlap?: boolean
  enabled?: boolean
}

/** Response of the write endpoints: whether a running daemon re-read the file */
export type SchedulerWriteResult = {
  path: string
  reload: { reloaded: boolean, changes: Record<string, string[]> | null, error: string | null }
}

// -- command line <-> argv ----------------------------------------------------

/** Split a command line into arguments, like a POSIX shell does for quotes and backslashes (no expansion). */
export const splitArgs = (line: string): string[] => {
  const args: string[] = []
  let cur = ''
  let inArg = false
  let quote: '"' | "'" | null = null
  for (let i = 0; i < line.length; i++) {
    const c = line[i]
    if (quote === "'") {
      if (c === "'") quote = null
      else cur += c
    } else if (quote === '"') {
      if (c === '"') quote = null
      else if (c === '\\' && i + 1 < line.length && '"\\$`'.includes(line[i + 1])) cur += line[++i]
      else cur += c
    } else if (c === '"' || c === "'") {
      quote = c
      inArg = true
    } else if (c === '\\' && i + 1 < line.length) {
      cur += line[++i]
      inArg = true
    } else if (/\s/.test(c)) {
      if (inArg) args.push(cur)
      cur = ''
      inArg = false
    } else {
      cur += c
      inArg = true
    }
  }
  if (quote) throw new Error(`Unclosed ${quote} quote`)
  if (inArg) args.push(cur)
  return args
}

/** Join arguments into a command line that splitArgs() turns back into the same list. */
export const joinArgs = (args: string[]): string =>
  args.map((a) => (a === '' ? "''" : /^[\w@%+=:,./$-]+$/.test(a) ? a : `'${a.replace(/'/g, `'\\''`)}'`)).join(' ')

// -- interval -----------------------------------------------------------------

const CRON_PRESETS: [string, string][] = [
  ['Every minute', '* * * * *'],
  ['Every 15 min', '*/15 * * * *'],
  ['Hourly', '0 * * * *'],
  ['Daily 9:00 UTC', '0 9 * * *'],
  ['Weekdays 9:00 UTC', '0 9 * * 1-5'],
]

const pad = (n: number) => String(n).padStart(2, '0')

/** ISO datetime -> value of an <input type="datetime-local"> (local time) */
const isoToLocalInput = (iso: string) => {
  const d = new Date(iso)
  if (isNaN(d.getTime())) return ''
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

// -- form state ---------------------------------------------------------------

type FormState = {
  name: string
  enabled: boolean
  intervalKind: 'cron' | 'at'
  cron: string
  at: string // datetime-local value
  targetKind: 'cmd' | 'module'
  cmd: string
  module: string
  params: string // one per line
  env: string // KEY=VALUE per line
  workingDir: string
  timeout: string
  allowOverlap: boolean
}

const toForm = (task?: SchedulerTaskInput | null): FormState => {
  const interval = task?.interval ?? 'cron:0 * * * *'
  const isAt = interval.startsWith('at:')
  return {
    name: task?.name ?? '',
    enabled: task?.enabled ?? true,
    intervalKind: isAt ? 'at' : 'cron',
    cron: isAt ? '0 * * * *' : interval.replace(/^cron:/, '').trim(),
    at: isAt ? isoToLocalInput(interval.slice(3).trim()) : '',
    targetKind: task?.module && !task?.cmd?.length ? 'module' : 'cmd',
    cmd: task?.cmd?.length ? joinArgs(task.cmd) : '',
    module: task?.module ?? '',
    params: (task?.params ?? []).join('\n'),
    env: Object.entries(task?.env ?? {}).map(([k, v]) => `${k}=${v}`).join('\n'),
    workingDir: task?.working_dir ?? '',
    timeout: task?.timeout ? String(task.timeout) : '',
    allowOverlap: !!task?.allow_overlap,
  }
}

const lines = (text: string) => text.split('\n').map((l) => l.trim()).filter(Boolean)

/** Build the request body; throws Error with a message for the user on invalid input. */
const toInput = (f: FormState): SchedulerTaskInput => {
  if (!f.name.trim()) throw new Error('Name is required')

  let interval: string
  if (f.intervalKind === 'cron') {
    if (f.cron.trim().split(/\s+/).length < 5) throw new Error('A cron expression has 5 fields, e.g. "0 9 * * *"')
    interval = `cron:${f.cron.trim()}`
  } else {
    const d = new Date(f.at)
    if (!f.at || isNaN(d.getTime())) throw new Error('Pick a date and time')
    interval = `at:${d.toISOString()}`
  }

  const env: Record<string, string> = {}
  for (const line of lines(f.env)) {
    const i = line.indexOf('=')
    if (i <= 0) throw new Error(`Invalid environment line "${line}", expected KEY=VALUE`)
    env[line.slice(0, i).trim()] = line.slice(i + 1)
  }

  let timeout: number | null = null
  if (f.timeout.trim()) {
    timeout = Number(f.timeout)
    if (!(timeout > 0)) throw new Error('Timeout must be a positive number of seconds')
  }

  const body: SchedulerTaskInput = {
    name: f.name.trim(),
    interval,
    enabled: f.enabled,
    env: Object.keys(env).length ? env : null,
    working_dir: f.workingDir.trim() || null,
    timeout,
    allow_overlap: f.allowOverlap,
  }
  if (f.targetKind === 'cmd') {
    const cmd = splitArgs(f.cmd)
    if (!cmd.length) throw new Error('Command is required')
    body.cmd = cmd
  } else {
    if (!f.module.trim()) throw new Error('Module is required')
    body.module = f.module.trim()
    const params = lines(f.params)
    body.params = params.length ? params : null
  }
  return body
}

/** Message of a failed request; FastAPI validation errors (422) have a list as detail */
const requestError = (err: any): string => {
  const detail = err?.response?.data?.detail
  if (Array.isArray(detail)) return detail.map((d) => `${(d.loc ?? []).slice(1).join('.')}: ${d.msg}`).join('; ')
  return err?.message || 'Unknown error'
}

// -- components ---------------------------------------------------------------

const Segmented = <T extends string>({ value, options, onChange }: {
  value: T
  options: [T, string][]
  onChange: (v: T) => void
}) => (
  <div className="inline-flex rounded-md border p-0.5">
    {options.map(([v, label]) => (
      <button key={v} type="button" onClick={() => onChange(v)}
              className={cn('rounded px-2.5 py-1 text-xs', value === v ? 'bg-secondary font-medium' : 'text-muted-foreground hover:text-foreground')}>
        {label}
      </button>
    ))}
  </div>
)

const FormRow = ({ label, htmlFor, hint, children }: {
  label: string
  htmlFor?: string
  hint?: React.ReactNode
  children: React.ReactNode
}) => (
  <div className="grid gap-1.5">
    <Label htmlFor={htmlFor}>{label}</Label>
    {children}
    {hint && <div className="text-xs text-muted-foreground">{hint}</div>}
  </div>
)

/**
 * Dialog to add a scheduled task (`task` null) or edit one.
 * Saves to the scheduler config through the API, which reloads a running daemon.
 */
const SchedulerTaskDialog = ({ open, onOpenChange, task, onSaved }: {
  open: boolean
  onOpenChange: (open: boolean) => void
  task: SchedulerTaskInput | null
  onSaved: (result: SchedulerWriteResult) => void
}) => {
  const { fetchJson } = useApi()
  const [form, setForm] = React.useState<FormState>(() => toForm(task))
  const [error, setError] = React.useState<string | null>(null)
  const [saving, setSaving] = React.useState(false)
  const isEdit = !!task

  // Reset whenever the dialog opens for a (different) task
  React.useEffect(() => {
    if (open) {
      setForm(toForm(task))
      setError(null)
    }
  }, [open, task])

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) => setForm((f) => ({ ...f, [key]: value }))

  // Live preview of how the command line is split into arguments
  let cmdPreview: string[] | null = null
  let cmdError: string | null = null
  if (form.targetKind === 'cmd' && form.cmd.trim()) {
    try {
      cmdPreview = splitArgs(form.cmd)
    } catch (err: any) {
      cmdError = err.message
    }
  }

  const save = async (e: React.FormEvent) => {
    e.preventDefault()
    let body: SchedulerTaskInput
    try {
      body = toInput(form)
    } catch (err: any) {
      setError(err.message)
      return
    }
    setSaving(true)
    setError(null)
    try {
      const url = isEdit ? `/api/v1/scheduler/tasks/${encodeURIComponent(task!.name)}` : '/api/v1/scheduler/tasks'
      const result = await fetchJson(url, {
        method: isEdit ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      onSaved(result)
      onOpenChange(false)
    } catch (err) {
      setError(requestError(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <form onSubmit={save} className="grid gap-4">
          <DialogHeader>
            <DialogTitle>{isEdit ? `Edit task "${task!.name}"` : 'Add scheduled task'}</DialogTitle>
            <DialogDescription>
              Saved to the scheduler config. A running daemon picks up the change right away.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 sm:grid-cols-[1fr_auto] sm:items-end">
            <FormRow label="Name" htmlFor="task-name">
              <Input id="task-name" value={form.name} onChange={(e) => set('name', e.target.value)}
                     placeholder="daily_summary" autoFocus={!isEdit} />
            </FormRow>
            <label className="flex h-9 items-center gap-2 text-sm">
              <Switch checked={form.enabled} onCheckedChange={(v) => set('enabled', v)} /> Enabled
            </label>
          </div>

          <FormRow label="Schedule" hint={form.intervalKind === 'cron'
            ? <>Cron fields: minute hour day-of-month month day-of-week, evaluated in UTC.</>
            : <>Runs once, at this time in your browser&apos;s time zone.</>}>
            <div className="flex flex-col gap-2">
              <Segmented value={form.intervalKind} onChange={(v) => set('intervalKind', v)}
                         options={[['cron', 'Repeating (cron)'], ['at', 'Once (at)']]} />
              {form.intervalKind === 'cron' ? (
                <>
                  <Input value={form.cron} onChange={(e) => set('cron', e.target.value)}
                         placeholder="0 9 * * *" className="font-mono" />
                  <div className="flex flex-wrap gap-1.5">
                    {CRON_PRESETS.map(([label, expr]) => (
                      <Button key={expr} type="button" size="sm" variant={form.cron.trim() === expr ? 'secondary' : 'outline'}
                              className="h-7 text-xs" onClick={() => set('cron', expr)}>{label}</Button>
                    ))}
                  </div>
                </>
              ) : (
                <Input type="datetime-local" value={form.at} onChange={(e) => set('at', e.target.value)} className="w-fit" />
              )}
            </div>
          </FormRow>

          <FormRow label="Run">
            <div className="flex flex-col gap-2">
              <Segmented value={form.targetKind} onChange={(v) => set('targetKind', v)}
                         options={[['cmd', 'Command'], ['module', 'Python callable']]} />
              {form.targetKind === 'cmd' ? (
                <>
                  <Input value={form.cmd} onChange={(e) => set('cmd', e.target.value)} className="font-mono"
                         placeholder={'$GEENII_BIN agent --name mac-bot "Remind me to drink water"'} />
                  <div className="text-xs text-muted-foreground">
                    Run directly, not through a shell. Quote arguments with spaces; <code>$VAR</code> is filled in from the daemon&apos;s environment.
                  </div>
                  {cmdError && <div className="text-xs text-destructive">{cmdError}</div>}
                  {cmdPreview && cmdPreview.length > 1 && (
                    <div className="flex flex-wrap gap-1">
                      {cmdPreview.map((a, i) => (
                        <span key={i} className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">{a || '""'}</span>
                      ))}
                    </div>
                  )}
                </>
              ) : (
                <>
                  <Input value={form.module} onChange={(e) => set('module', e.target.value)}
                         placeholder="geenii.core.tasks.run_agent" className="font-mono" />
                  <Textarea value={form.params} onChange={(e) => set('params', e.target.value)} rows={2}
                            placeholder="Params, one per line" className="font-mono text-xs" />
                </>
              )}
            </div>
          </FormRow>

          <details className="group rounded-md border px-3 py-2" open={!!(form.env || form.workingDir || form.timeout || form.allowOverlap) || undefined}>
            <summary className="cursor-pointer text-sm font-medium">Advanced</summary>
            <div className="mt-3 grid gap-4">
              <FormRow label="Environment" hint="One KEY=VALUE per line.">
                <Textarea value={form.env} onChange={(e) => set('env', e.target.value)} rows={2}
                          placeholder="SOME_VAR=value" className="font-mono text-xs" />
              </FormRow>
              {form.targetKind === 'cmd' && (
                <FormRow label="Working directory" htmlFor="task-cwd">
                  <Input id="task-cwd" value={form.workingDir} onChange={(e) => set('workingDir', e.target.value)}
                         placeholder="Default: the daemon's working directory" className="font-mono" />
                </FormRow>
              )}
              <div className="grid gap-4 sm:grid-cols-2 sm:items-end">
                <FormRow label="Timeout (seconds)" htmlFor="task-timeout">
                  <Input id="task-timeout" type="number" min={0} step="any" value={form.timeout}
                         onChange={(e) => set('timeout', e.target.value)} placeholder="No limit" />
                </FormRow>
                <label className="flex h-9 items-center gap-2 text-sm">
                  <Switch checked={form.allowOverlap} onCheckedChange={(v) => set('allowOverlap', v)} />
                  Allow overlapping runs
                </label>
              </div>
            </div>
          </details>

          {error && <div className="rounded-md border border-destructive/50 px-3 py-2 text-sm text-destructive">{error}</div>}

          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit" disabled={saving}>{saving ? 'Saving…' : isEdit ? 'Save' : 'Add task'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export default SchedulerTaskDialog
