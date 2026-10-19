import React from 'react'
import { CheckIcon, KeyRoundIcon, LoaderIcon, PlusIcon, SaveIcon, Trash2Icon, XIcon } from 'lucide-react'
import { AgentEnvType } from '@/app/agents/agent-types.ts'
import { Button } from '@/components/ui/button.tsx'
import { Input } from '@/components/ui/input.tsx'
import { Label } from '@/components/ui/label.tsx'
import { Skeleton } from '@/components/ui/skeleton.tsx'
import { useApi } from '@/context/api-context.tsx'

const KEY_PATTERN = /^[A-Za-z_][A-Za-z0-9_]*$/

type VarRow = { id: string, key: string, value: string }

let rowCounter = 0
const rowId = () => `env-${++rowCounter}`

const rowsFromVars = (vars: Record<string, string>): VarRow[] =>
  Object.entries(vars).map(([key, value]) => ({ id: rowId(), key, value }))

const validateRows = (rows: VarRow[]): string | null => {
  const keys = rows.map((r) => r.key.trim()).filter(Boolean)
  if (new Set(keys).size !== keys.length) return 'Variable names must be unique.'
  if (rows.some((r) => !r.key.trim() && r.value)) return 'Every variable needs a name.'
  const invalid = keys.find((k) => !KEY_PATTERN.test(k))
  return invalid ? `"${invalid}" is not a valid name. Use letters, digits and _, not starting with a digit.` : null
}

/**
 * The agent's environment variables and secrets, saved right away to their own files
 * (not the spec file). Secret values are write-only.
 */
const AgentEnvEditor = ({ agentName }: { agentName: string }) => {
  const { fetchJson } = useApi()
  const base = `/api/v1/agents/${encodeURIComponent(agentName)}/env`

  const [loading, setLoading] = React.useState(true)
  const [loadError, setLoadError] = React.useState<string | null>(null)
  const [rows, setRows] = React.useState<VarRow[]>([])
  const [savedVars, setSavedVars] = React.useState<Record<string, string>>({})
  const [secrets, setSecrets] = React.useState<string[]>([])

  const [savingVars, setSavingVars] = React.useState(false)
  const [varsSaved, setVarsSaved] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const [secretKey, setSecretKey] = React.useState('')
  const [secretValue, setSecretValue] = React.useState('')
  const [replacing, setReplacing] = React.useState<string | null>(null)
  const [busySecret, setBusySecret] = React.useState<string | null>(null)

  const apply = (env: AgentEnvType) => {
    setSavedVars(env.vars)
    setRows(rowsFromVars(env.vars))
    setSecrets(env.secrets)
  }

  React.useEffect(() => {
    let cancelled = false
    ;(fetchJson(base) as Promise<AgentEnvType>)
      .then((env) => { if (!cancelled) apply(env) })
      .catch((err) => { if (!cancelled) setLoadError(err?.message || 'Unknown error') })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [fetchJson, base])

  const rowsError = validateRows(rows)
  const currentVars = Object.fromEntries(rows.filter((r) => r.key.trim()).map((r) => [r.key.trim(), r.value]))
  const varsDirty = JSON.stringify(currentVars) !== JSON.stringify(savedVars)
  const updateRow = (id: string, patch: Partial<VarRow>) => setRows((rs) => rs.map((r) => (r.id === id ? { ...r, ...patch } : r)))

  const saveVars = async () => {
    if (rowsError) return
    setSavingVars(true)
    setError(null)
    try {
      apply(await fetchJson(`${base}/vars`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(currentVars),
      }))
      setVarsSaved(true)
      setTimeout(() => setVarsSaved(false), 1500)
    } catch (err: any) {
      setError(err?.message || String(err))
    } finally {
      setSavingVars(false)
    }
  }

  const putSecret = async (key: string, value: string) => {
    setBusySecret(key)
    setError(null)
    try {
      const env: AgentEnvType = await fetchJson(`${base}/secrets/${encodeURIComponent(key)}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ value }),
      })
      setSecrets(env.secrets)
      setSecretKey('')
      setSecretValue('')
      setReplacing(null)
    } catch (err: any) {
      setError(err?.message || String(err))
    } finally {
      setBusySecret(null)
    }
  }

  const deleteSecret = async (key: string) => {
    if (!window.confirm(`Delete the secret ${key}?`)) return
    setBusySecret(key)
    setError(null)
    try {
      const env: AgentEnvType = await fetchJson(`${base}/secrets/${encodeURIComponent(key)}`, { method: 'DELETE' })
      setSecrets(env.secrets)
    } catch (err: any) {
      setError(err?.message || String(err))
    } finally {
      setBusySecret(null)
    }
  }

  const newKey = secretKey.trim()
  const newKeyError = newKey && !KEY_PATTERN.test(newKey) ? 'Use letters, digits and _, not starting with a digit.' : null

  if (loading) {
    return <div className="flex flex-col gap-3"><Skeleton className="h-9 w-full" /><Skeleton className="h-24 w-full" /></div>
  }
  if (loadError) {
    return <div className="rounded-lg border border-destructive/50 p-3 text-sm text-destructive">Failed to load the environment: {loadError}</div>
  }

  return (
    <div className="flex flex-col gap-6">
      <p className="text-xs text-muted-foreground">
        Passed to the agent's tool calls. Stored in <span className="font-mono">~/.geenii/agents/{agentName}.vars.env</span> and{' '}
        <span className="font-mono">{agentName}.secrets.env</span>, not in the spec file, and saved right away.
        Applies to new conversations.
      </p>
      {error && <div className="rounded-md border border-destructive/50 p-3 text-sm text-destructive">{error}</div>}

      <section className="flex flex-col gap-2">
        <Label>Variables</Label>
        {rows.length === 0 && <p className="text-sm text-muted-foreground">No variables.</p>}
        {rows.map((r) => (
          <div key={r.id} className="flex items-center gap-1.5">
            <Input className="w-2/5 font-mono" value={r.key} placeholder="NAME" onChange={(e) => updateRow(r.id, { key: e.target.value })} />
            <Input className="flex-1 font-mono" value={r.value} placeholder="value" onChange={(e) => updateRow(r.id, { value: e.target.value })} />
            <Button type="button" size="icon" variant="ghost" title="Remove variable"
                    onClick={() => setRows((rs) => rs.filter((x) => x.id !== r.id))}>
              <Trash2Icon />
            </Button>
          </div>
        ))}
        {rowsError && <p className="text-xs text-destructive">{rowsError}</p>}
        <div className="flex items-center justify-between gap-2">
          <Button type="button" size="sm" variant="ghost" onClick={() => setRows((rs) => [...rs, { id: rowId(), key: '', value: '' }])}>
            <PlusIcon /> Add variable
          </Button>
          <Button type="button" size="sm" disabled={!varsDirty || !!rowsError || savingVars} onClick={saveVars}>
            {savingVars ? <LoaderIcon className="animate-spin" /> : varsSaved ? <CheckIcon /> : <SaveIcon />}
            {varsSaved ? 'Saved' : 'Save variables'}
          </Button>
        </div>
      </section>

      <section className="flex flex-col gap-2">
        <Label>Secrets</Label>
        <p className="text-xs text-muted-foreground">Sensitive variables. Their values can be set or replaced, but not shown, and are redacted in logs.</p>
        {secrets.length === 0 && <p className="text-sm text-muted-foreground">No secrets.</p>}
        {secrets.map((key) => (
          <div key={key} className="flex items-center gap-1.5">
            <span className="flex w-2/5 items-center gap-1.5 truncate font-mono text-sm"><KeyRoundIcon size={14} className="shrink-0" /> {key}</span>
            {replacing === key ? (
              <>
                <Input type="password" className="flex-1 font-mono" autoFocus autoComplete="new-password" placeholder="new value"
                       value={secretValue} onChange={(e) => setSecretValue(e.target.value)} />
                <Button type="button" size="icon" variant="ghost" title="Save" disabled={busySecret === key}
                        onClick={() => putSecret(key, secretValue)}>
                  {busySecret === key ? <LoaderIcon className="animate-spin" /> : <CheckIcon />}
                </Button>
                <Button type="button" size="icon" variant="ghost" title="Cancel" onClick={() => { setReplacing(null); setSecretValue('') }}>
                  <XIcon />
                </Button>
              </>
            ) : (
              <>
                <span className="flex-1 font-mono text-sm text-muted-foreground">••••••••</span>
                <Button type="button" size="sm" variant="outline" onClick={() => { setReplacing(key); setSecretValue('') }}>Replace</Button>
                <Button type="button" size="icon" variant="ghost" title="Delete secret" disabled={busySecret === key}
                        onClick={() => deleteSecret(key)}>
                  <Trash2Icon />
                </Button>
              </>
            )}
          </div>
        ))}
        {replacing === null && (
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-1.5">
              <Input className="w-2/5 font-mono" placeholder="NAME" value={secretKey} aria-invalid={!!newKeyError}
                     onChange={(e) => setSecretKey(e.target.value)} />
              <Input type="password" className="flex-1 font-mono" autoComplete="new-password" placeholder="value"
                     value={secretValue} onChange={(e) => setSecretValue(e.target.value)} />
              <Button type="button" size="sm" variant="outline" disabled={!newKey || !!newKeyError || busySecret !== null}
                      title={secrets.includes(newKey) ? 'Replaces the existing secret' : undefined}
                      onClick={() => putSecret(newKey, secretValue)}>
                {busySecret === newKey ? <LoaderIcon className="animate-spin" /> : <PlusIcon />} {secrets.includes(newKey) ? 'Replace' : 'Add'}
              </Button>
            </div>
            {newKeyError && <p className="text-xs text-destructive">{newKeyError}</p>}
          </div>
        )}
      </section>
    </div>
  )
}

export default AgentEnvEditor
