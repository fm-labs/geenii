import * as React from 'react'
import { Button } from '@/components/ui/button.tsx'
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from '@/components/ui/dialog.tsx'
import { Input } from '@/components/ui/input.tsx'
import { Switch } from '@/components/ui/switch.tsx'
import { Textarea } from '@/components/ui/textarea.tsx'
import { useApi } from '@/context/api-context.tsx'
import { FormRow, joinArgs, requestError, splitArgs } from '@/app/console/components/scheduler-task-dialog.tsx'

/** Body of POST /api/v1/supervisor/services and PUT /api/v1/supervisor/services/{name}, see ServiceInput in supervisor_routes.py */
export type SupervisorServiceInput = {
  name: string
  cmd: string[]
  restart?: boolean
  env?: Record<string, string> | null
  cwd?: string | null
  capture_output?: boolean
  enabled?: boolean
}

/** Response of the write endpoints: whether a running daemon re-applied the file */
export type SupervisorWriteResult = {
  path: string
  reload: { reloaded: boolean, changes: Record<string, string[]> | null, error: string | null }
}

type FormState = {
  name: string
  enabled: boolean
  cmd: string
  restart: boolean
  env: string // KEY=VALUE per line
  cwd: string
  captureOutput: boolean
}

const toForm = (s?: SupervisorServiceInput | null): FormState => ({
  name: s?.name ?? '',
  enabled: s?.enabled ?? true,
  cmd: s?.cmd?.length ? joinArgs(s.cmd) : '',
  restart: s?.restart ?? true,
  env: Object.entries(s?.env ?? {}).map(([k, v]) => `${k}=${v}`).join('\n'),
  cwd: s?.cwd ?? '',
  captureOutput: s?.capture_output ?? true,
})

/** Build the request body; throws Error with a message for the user on invalid input. */
const toInput = (f: FormState): SupervisorServiceInput => {
  if (!f.name.trim()) throw new Error('Name is required')
  const cmd = splitArgs(f.cmd)
  if (!cmd.length) throw new Error('Command is required')
  const env: Record<string, string> = {}
  for (const line of f.env.split('\n').map((l) => l.trim()).filter(Boolean)) {
    const i = line.indexOf('=')
    if (i <= 0) throw new Error(`Invalid environment line "${line}", expected KEY=VALUE`)
    env[line.slice(0, i).trim()] = line.slice(i + 1)
  }
  return {
    name: f.name.trim(),
    cmd,
    enabled: f.enabled,
    restart: f.restart,
    env: Object.keys(env).length ? env : null,
    cwd: f.cwd.trim() || null,
    capture_output: f.captureOutput,
  }
}

/**
 * Dialog to add a service (`service` null) or edit one.
 * Saves to the services config through the API, which makes a running daemon apply it.
 */
const SupervisorServiceDialog = ({ open, onOpenChange, service, onSaved }: {
  open: boolean
  onOpenChange: (open: boolean) => void
  service: SupervisorServiceInput | null
  onSaved: (result: SupervisorWriteResult) => void
}) => {
  const { fetchJson } = useApi()
  const [form, setForm] = React.useState<FormState>(() => toForm(service))
  const [error, setError] = React.useState<string | null>(null)
  const [saving, setSaving] = React.useState(false)
  const isEdit = !!service

  // Reset whenever the dialog opens for a (different) service
  React.useEffect(() => {
    if (open) {
      setForm(toForm(service))
      setError(null)
    }
  }, [open, service])

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) => setForm((f) => ({ ...f, [key]: value }))

  // Live preview of how the command line is split into arguments
  let cmdPreview: string[] | null = null
  let cmdError: string | null = null
  if (form.cmd.trim()) {
    try {
      cmdPreview = splitArgs(form.cmd)
    } catch (err: any) {
      cmdError = err.message
    }
  }

  const save = async (e: React.FormEvent) => {
    e.preventDefault()
    let body: SupervisorServiceInput
    try {
      body = toInput(form)
    } catch (err: any) {
      setError(err.message)
      return
    }
    setSaving(true)
    setError(null)
    try {
      const url = isEdit ? `/api/v1/supervisor/services/${encodeURIComponent(service!.name)}` : '/api/v1/supervisor/services'
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
            <DialogTitle>{isEdit ? `Edit service "${service!.name}"` : 'Add service'}</DialogTitle>
            <DialogDescription>
              Saved to the services config. A running daemon starts, or restarts, the service right away.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 sm:grid-cols-[1fr_auto] sm:items-end">
            <FormRow label="Name" htmlFor="service-name">
              <Input id="service-name" value={form.name} onChange={(e) => set('name', e.target.value)}
                     placeholder="web" autoFocus={!isEdit} />
            </FormRow>
            <label className="flex h-9 items-center gap-2 text-sm">
              <Switch checked={form.enabled} onCheckedChange={(v) => set('enabled', v)} /> Enabled
            </label>
          </div>

          <FormRow label="Command" htmlFor="service-cmd"
                   hint={<>Run directly, not through a shell (use <code>sh -c &apos;…&apos;</code> for shell syntax). Quote arguments with spaces; <code>$VAR</code> is filled in from the daemon&apos;s environment.</>}>
            <Input id="service-cmd" value={form.cmd} onChange={(e) => set('cmd', e.target.value)} className="font-mono"
                   autoCorrect="off" autoCapitalize="off" spellCheck={false}
                   placeholder="python -m http.server 8000" />
            {cmdError && <div className="text-xs text-destructive">{cmdError}</div>}
            {cmdPreview && cmdPreview.length > 1 && (
              <div className="flex flex-wrap gap-1">
                {cmdPreview.map((a, i) => (
                  <span key={i} className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">{a || '""'}</span>
                ))}
              </div>
            )}
          </FormRow>

          <label className="flex items-center gap-2 text-sm">
            <Switch checked={form.restart} onCheckedChange={(v) => set('restart', v)} />
            Restart when it exits
            <span className="text-xs text-muted-foreground">(off: run once per daemon start)</span>
          </label>

          <details className="group rounded-md border px-3 py-2" open={!!(form.env || form.cwd || !form.captureOutput) || undefined}>
            <summary className="cursor-pointer text-sm font-medium">Advanced</summary>
            <div className="mt-3 grid gap-4">
              <FormRow label="Environment" hint="One KEY=VALUE per line, added to the daemon's environment.">
                <Textarea value={form.env} onChange={(e) => set('env', e.target.value)} rows={2}
                          placeholder="PYTHONUNBUFFERED=1" className="font-mono text-xs" />
              </FormRow>
              <FormRow label="Working directory" htmlFor="service-cwd">
                <Input id="service-cwd" value={form.cwd} onChange={(e) => set('cwd', e.target.value)}
                       placeholder="Default: the daemon's working directory" className="font-mono" />
              </FormRow>
              <label className="flex items-center gap-2 text-sm">
                <Switch checked={form.captureOutput} onCheckedChange={(v) => set('captureOutput', v)} />
                Capture output (shown in the service log)
              </label>
            </div>
          </details>

          {error && <div className="rounded-md border border-destructive/50 px-3 py-2 text-sm text-destructive">{error}</div>}

          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit" disabled={saving}>{saving ? 'Saving…' : isEdit ? 'Save' : 'Add service'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export default SupervisorServiceDialog
