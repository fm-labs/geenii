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
import { splitArgs } from '@/app/console/components/scheduler-task-dialog.tsx'
import type { ProcessInfo } from '@/app/console/components/process-manager-view.tsx'

/** Parse KEY=VALUE lines; throws on an invalid line */
const parseEnv = (text: string): Record<string, string> | null => {
  const env: Record<string, string> = {}
  for (const line of text.split('\n')) {
    const t = line.trim()
    if (!t) continue
    const i = t.indexOf('=')
    if (i < 1) throw new Error(`Invalid environment line: ${t}`)
    env[t.slice(0, i)] = t.slice(i + 1)
  }
  return Object.keys(env).length ? env : null
}

/** Start a background process (POST /api/v1/pm/processes) */
const ProcessStartDialog = ({ open, onOpenChange, onStarted }: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onStarted: (process: ProcessInfo) => void
}) => {
  const { fetchJson } = useApi()
  const [command, setCommand] = React.useState('')
  const [shell, setShell] = React.useState(true)
  const [cwd, setCwd] = React.useState('')
  const [pid, setPid] = React.useState('')
  const [env, setEnv] = React.useState('')
  const [error, setError] = React.useState<string | null>(null)
  const [saving, setSaving] = React.useState(false)

  React.useEffect(() => {
    if (open) {
      setError(null)
      setPid('')
    }
  }, [open])

  let argv: string[] | null = null
  let argvError: string | null = null
  if (!shell && command.trim()) {
    try {
      argv = splitArgs(command)
    } catch (err) {
      argvError = err.message
    }
  }

  const submit = async (ev: React.FormEvent) => {
    ev.preventDefault()
    setError(null)
    let body
    try {
      if (!command.trim()) throw new Error('Enter a command')
      if (argvError) throw new Error(argvError)
      body = {
        // A string runs through the shell, a list is executed directly
        command: shell ? command.trim() : argv,
        cwd: cwd.trim() || null,
        pid: pid.trim() || null,
        env: parseEnv(env),
      }
    } catch (err) {
      setError(err.message)
      return
    }
    setSaving(true)
    try {
      const process: ProcessInfo = await fetchJson('/api/v1/pm/processes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      onOpenChange(false)
      onStarted(process)
    } catch (err) {
      setError(err?.message || 'Unknown error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <form onSubmit={submit} className="flex flex-col gap-4">
          <DialogHeader>
            <DialogTitle>Start process</DialogTitle>
            <DialogDescription>
              Runs in the background in the geenii daemon; its output is kept until the logs are deleted.
            </DialogDescription>
          </DialogHeader>

          <div className="flex flex-col gap-2">
            <Label htmlFor="pm-cmd">Command</Label>
            <Input id="pm-cmd" className="font-mono" autoFocus value={command} onChange={(e) => setCommand(e.target.value)}
                   placeholder={shell ? 'echo hello && sleep 5' : 'python -m http.server 8000'} />
            <div className="flex items-center gap-2">
              <Switch id="pm-shell" size="sm" checked={shell} onCheckedChange={setShell} />
              <Label htmlFor="pm-shell" className="text-xs font-normal">Run through the shell</Label>
            </div>
            {!shell && (argvError
              ? <div className="text-xs text-destructive">{argvError}</div>
              : argv && <div className="break-all font-mono text-xs text-muted-foreground">{JSON.stringify(argv)}</div>)}
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="flex flex-col gap-2">
              <Label htmlFor="pm-cwd">Working directory</Label>
              <Input id="pm-cwd" className="font-mono" value={cwd} onChange={(e) => setCwd(e.target.value)} placeholder="daemon's directory" />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="pm-pid">Process ID</Label>
              <Input id="pm-pid" className="font-mono" value={pid} onChange={(e) => setPid(e.target.value)} placeholder="generated" />
            </div>
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="pm-env">Environment</Label>
            <Textarea id="pm-env" className="min-h-16 font-mono text-xs" value={env} onChange={(e) => setEnv(e.target.value)}
                      placeholder={'KEY=value\nOTHER=value'} />
          </div>

          {error && <div className="text-sm text-destructive">{error}</div>}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit" disabled={saving}>{saving ? 'Starting…' : 'Start'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export default ProcessStartDialog
