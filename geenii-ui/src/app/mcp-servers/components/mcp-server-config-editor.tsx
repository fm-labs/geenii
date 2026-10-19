import React from 'react'
import {
  BracesIcon, ChevronRightIcon, EyeIcon, EyeOffIcon, GlobeIcon, KeyRoundIcon, ListIcon, LoaderIcon, PlusIcon,
  SaveIcon, TerminalIcon, Trash2Icon,
} from 'lucide-react'
import { Button } from '@/components/ui/button.tsx'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible.tsx'
import { Input } from '@/components/ui/input.tsx'
import { Label } from '@/components/ui/label.tsx'
import { Textarea } from '@/components/ui/textarea.tsx'
import { cn } from 'cn'

/** Placeholder the API returns instead of env values; sent back as-is to mean "keep the stored value" */
export const MASKED_VALUE = '********'

type Transport = 'stdio' | 'http' | 'sse'
type ArgRow = { id: string, value: string }
type KeyValueRow = { id: string, key: string, value: string, masked?: boolean }

type EditorState = {
  name: string
  description: string
  transport: Transport
  command: string
  args: ArgRow[]
  env: KeyValueRow[]
  cwd: string
  url: string
  headers: KeyValueRow[]
  timeout: string
  legacy: boolean
  /** Keys the editor has no field for (keep_alive, tools, authentication, ...), passed through unchanged */
  extra: Record<string, any>
}

const KNOWN_KEYS = ['type', 'transport', 'command', 'args', 'env', 'cwd', 'url', 'headers', 'description', 'timeout', 'legacy']
const NAME_PATTERN = /^[A-Za-z0-9_-]+$/
const ENV_KEY_PATTERN = /^[A-Za-z_][A-Za-z0-9_]*$/
const SECRET_KEY_PATTERN = /key|token|secret|pass|auth|cred/i

let rowCounter = 0
const rowId = () => `row-${++rowCounter}`

/** Splits a shell-like command line into words, honouring single and double quotes */
export const splitCommandLine = (line: string): string[] => {
  const words: string[] = []
  let current = ''
  let quote: string | null = null
  let quoted = false
  for (const ch of line.trim()) {
    if (quote) {
      if (ch === quote) quote = null
      else current += ch
    } else if (ch === '"' || ch === "'") {
      quote = ch
      quoted = true
    } else if (/\s/.test(ch)) {
      if (current || quoted) words.push(current)
      current = ''
      quoted = false
    } else {
      current += ch
    }
  }
  if (current || quoted) words.push(current)
  return words
}

const quoteArg = (arg: string) => (arg === '' || /[\s"']/.test(arg) ? `'${arg.replace(/'/g, `'\\''`)}'` : arg)

const toRows = (map?: Record<string, string>): KeyValueRow[] =>
  Object.entries(map || {}).map(([key, value]) =>
    value === MASKED_VALUE ? { id: rowId(), key, value: '', masked: true } : { id: rowId(), key, value: String(value) })

const fromRows = (rows: KeyValueRow[]): Record<string, string> | undefined => {
  const entries = rows
    .filter((r) => r.key.trim())
    .map((r) => [r.key.trim(), r.masked && r.value === '' ? MASKED_VALUE : r.value] as const)
  return entries.length > 0 ? Object.fromEntries(entries) : undefined
}

const stateFromConfig = (name: string, config: McpServerConfig): EditorState => {
  const transport: Transport = config.command || config.transport === 'stdio' || config.type === 'stdio'
    ? 'stdio'
    : (config.transport === 'sse' || config.type === 'sse' ? 'sse' : 'http')
  const extra = Object.fromEntries(Object.entries(config).filter(([k]) => !KNOWN_KEYS.includes(k) && k !== 'name'))
  return {
    name,
    description: config.description || '',
    transport,
    command: config.command || '',
    args: (config.args || []).map((value) => ({ id: rowId(), value: String(value) })),
    env: toRows(config.env),
    cwd: config.cwd || '',
    url: config.url || '',
    headers: toRows(config.headers),
    timeout: config.timeout != null ? String(config.timeout) : '',
    legacy: !!config.legacy,
    extra,
  }
}

/** Builds the mcp.json entry; only the fields of the selected transport are included */
const configFromState = (s: EditorState): McpServerConfig => {
  const config: McpServerConfig = {}
  if (s.description.trim()) config.description = s.description.trim()
  if (s.transport === 'stdio') {
    config.command = s.command.trim()
    const args = s.args.map((a) => a.value).filter((a) => a !== '')
    if (args.length > 0) config.args = args
    const env = fromRows(s.env)
    if (env) config.env = env
    if (s.cwd.trim()) config.cwd = s.cwd.trim()
  } else {
    config.url = s.url.trim()
    config.transport = s.transport
    const headers = fromRows(s.headers)
    if (headers) config.headers = headers
  }
  if (s.timeout.trim()) config.timeout = Number(s.timeout)
  if (s.legacy) config.legacy = true
  return { ...config, ...s.extra }
}

type Errors = Partial<Record<'name' | 'command' | 'url' | 'timeout' | 'env' | 'headers', string>>

const validateRows = (rows: KeyValueRow[], keyPattern?: RegExp): string | undefined => {
  const keys = rows.map((r) => r.key.trim()).filter(Boolean)
  if (rows.some((r) => !r.key.trim() && r.value)) return 'Every value needs a name.'
  if (keyPattern && keys.some((k) => !keyPattern.test(k))) return 'Names may only contain letters, digits and _, and must not start with a digit.'
  if (new Set(keys).size !== keys.length) return 'Names must be unique.'
  return undefined
}

const validate = (s: EditorState, takenNames: string[]): Errors => {
  const errors: Errors = {}
  const name = s.name.trim()
  if (!name) errors.name = 'A name is required.'
  else if (!NAME_PATTERN.test(name)) errors.name = 'Use letters, digits, - and _ only.'
  else if (takenNames.includes(name)) errors.name = `A server named "${name}" already exists.`

  if (s.transport === 'stdio') {
    if (!s.command.trim()) errors.command = 'A command is required.'
    errors.env = validateRows(s.env, ENV_KEY_PATTERN)
  } else {
    if (!s.url.trim()) errors.url = 'A URL is required.'
    else {
      try {
        const url = new URL(s.url.trim())
        if (url.protocol !== 'http:' && url.protocol !== 'https:') errors.url = 'The URL must start with http:// or https://.'
      } catch {
        errors.url = 'This is not a valid URL.'
      }
    }
    errors.headers = validateRows(s.headers)
  }
  if (s.timeout.trim() && !(Number.isInteger(Number(s.timeout)) && Number(s.timeout) > 0)) {
    errors.timeout = 'The timeout must be a whole number of milliseconds.'
  }
  return Object.fromEntries(Object.entries(errors).filter(([, v]) => v)) as Errors
}

const STDIO_PRESETS = [
  { label: 'Docker', command: 'docker', args: ['run', '-i', '--rm', 'mcp/<image>'] },
  { label: 'npx', command: 'npx', args: ['-y', '<package>'] },
  { label: 'uvx', command: 'uvx', args: ['<package>'] },
]

/* ---------- small building blocks ---------- */

const Field = ({ label, htmlFor, hint, error, children, className }: {
  label: string, htmlFor?: string, hint?: React.ReactNode, error?: string, children: React.ReactNode, className?: string
}) => (
  <div className={cn('flex flex-col gap-1.5', className)}>
    <Label htmlFor={htmlFor}>{label}</Label>
    {children}
    {error
      ? <p className="text-xs text-destructive">{error}</p>
      : hint && <p className="text-xs text-muted-foreground">{hint}</p>}
  </div>
)

function Segmented<T extends string>({ value, onChange, options, className }: {
  value: T
  onChange: (value: T) => void
  options: { value: T, label: string, description?: string, icon?: React.ReactNode }[]
  className?: string
}) {
  return (
    <div role="radiogroup" className={cn('grid gap-2', className)} style={{ gridTemplateColumns: `repeat(${options.length}, minmax(0, 1fr))` }}>
      {options.map((opt) => (
        <button key={opt.value} type="button" role="radio" aria-checked={value === opt.value}
                onClick={() => onChange(opt.value)}
                className={cn('flex cursor-pointer items-start gap-2 rounded-md border px-3 py-2 text-left text-sm transition-colors hover:bg-muted/50',
                  value === opt.value && 'border-primary bg-muted ring-1 ring-primary')}>
          {opt.icon && <span className="mt-0.5 shrink-0">{opt.icon}</span>}
          <span className="min-w-0">
            <span className="block font-medium">{opt.label}</span>
            {opt.description && <span className="block text-xs text-muted-foreground">{opt.description}</span>}
          </span>
        </button>
      ))}
    </div>
  )
}

const ArgsEditor = ({ args, onChange }: { args: ArgRow[], onChange: (args: ArgRow[]) => void }) => {
  const refs = React.useRef<Record<string, HTMLInputElement | null>>({})
  const [focusId, setFocusId] = React.useState<string | null>(null)

  React.useEffect(() => {
    if (focusId) refs.current[focusId]?.focus()
  }, [focusId])

  const add = (index = args.length) => {
    const row = { id: rowId(), value: '' }
    onChange([...args.slice(0, index), row, ...args.slice(index)])
    setFocusId(row.id)
  }

  return (
    <div className="flex flex-col gap-1.5">
      {args.map((arg, i) => (
        <div key={arg.id} className="flex items-center gap-1.5">
          <span className="w-6 shrink-0 text-right font-mono text-xs text-muted-foreground">{i + 1}</span>
          <Input ref={(el) => { refs.current[arg.id] = el }} className="font-mono" value={arg.value}
                 placeholder="argument"
                 onChange={(e) => onChange(args.map((a) => (a.id === arg.id ? { ...a, value: e.target.value } : a)))}
                 onKeyDown={(e) => {
                   if (e.key === 'Enter') {
                     e.preventDefault()
                     add(i + 1)
                   }
                 }}
                 onPaste={(e) => {
                   // pasting "a b c" into an argument splits it into several arguments
                   const words = splitCommandLine(e.clipboardData.getData('text'))
                   if (words.length > 1 && arg.value === '') {
                     e.preventDefault()
                     onChange([...args.slice(0, i), ...words.map((value) => ({ id: rowId(), value })), ...args.slice(i + 1)])
                   }
                 }} />
          <Button type="button" size="icon" variant="ghost" title="Remove argument"
                  onClick={() => onChange(args.filter((a) => a.id !== arg.id))}>
            <Trash2Icon />
          </Button>
        </div>
      ))}
      <Button type="button" size="sm" variant="outline" className="self-start" onClick={() => add()}>
        <PlusIcon /> Add argument
      </Button>
    </div>
  )
}

const KeyValueEditor = ({ rows, onChange, keyPlaceholder, valuePlaceholder, addLabel }: {
  rows: KeyValueRow[]
  onChange: (rows: KeyValueRow[]) => void
  keyPlaceholder: string
  valuePlaceholder: string
  addLabel: string
}) => {
  const [revealed, setRevealed] = React.useState<Record<string, boolean>>({})
  const update = (id: string, patch: Partial<KeyValueRow>) => onChange(rows.map((r) => (r.id === id ? { ...r, ...patch } : r)))

  return (
    <div className="flex flex-col gap-1.5">
      {rows.map((row) => {
        const secret = SECRET_KEY_PATTERN.test(row.key)
        const hidden = secret && !revealed[row.id]
        return (
          <div key={row.id} className="flex items-center gap-1.5">
            <Input className="w-2/5 font-mono" value={row.key} placeholder={keyPlaceholder}
                   onChange={(e) => update(row.id, { key: e.target.value })}
                   onPaste={(e) => {
                     // pasting KEY=value lines (e.g. from a .env file) adds one row per line
                     const lines = e.clipboardData.getData('text').split(/\r?\n/).map((l) => l.trim()).filter((l) => l && !l.startsWith('#'))
                     if (!lines.some((l) => l.includes('=') || l.includes(':'))) return
                     e.preventDefault()
                     const pasted = lines.map((line) => {
                       const sep = line.search(/[=:]/)
                       const key = (sep < 0 ? line : line.slice(0, sep)).replace(/^export\s+/, '').trim()
                       const value = sep < 0 ? '' : line.slice(sep + 1).trim().replace(/^(["'])(.*)\1$/, '$2')
                       return { id: rowId(), key, value }
                     })
                     const index = rows.findIndex((r) => r.id === row.id)
                     const keep = row.key || row.value ? [row] : []
                     onChange([...rows.slice(0, index), ...keep, ...pasted, ...rows.slice(index + 1)])
                   }} />
            <div className="relative flex-1">
              <Input className={cn('font-mono', secret && 'pr-9')} type={hidden ? 'password' : 'text'} value={row.value}
                     placeholder={row.masked ? 'unchanged' : valuePlaceholder}
                     autoComplete="off"
                     onChange={(e) => update(row.id, { value: e.target.value })} />
              {secret && (
                <button type="button" title={hidden ? 'Show value' : 'Hide value'}
                        className="absolute right-2 top-1/2 -translate-y-1/2 cursor-pointer text-muted-foreground hover:text-foreground"
                        onClick={() => setRevealed({ ...revealed, [row.id]: !revealed[row.id] })}>
                  {hidden ? <EyeIcon size={16} /> : <EyeOffIcon size={16} />}
                </button>
              )}
            </div>
            <Button type="button" size="icon" variant="ghost" title="Remove"
                    onClick={() => onChange(rows.filter((r) => r.id !== row.id))}>
              <Trash2Icon />
            </Button>
          </div>
        )
      })}
      <Button type="button" size="sm" variant="outline" className="self-start"
              onClick={() => onChange([...rows, { id: rowId(), key: '', value: '' }])}>
        <PlusIcon /> {addLabel}
      </Button>
    </div>
  )
}

/* ---------- editor ---------- */

export type McpServerConfigEditorProps = {
  /** Name of the server being edited; omit to create a new server */
  serverName?: string
  /** Existing config of the server being edited (values may be masked) */
  initialConfig?: McpServerConfig
  /** Names already in use, to reject duplicates */
  existingNames?: string[]
  /** Called with the new entry; a thrown error is shown in the editor */
  onSubmit: (name: string, config: McpServerConfig) => Promise<void> | void
  onCancel?: () => void
}

/** Form for one mcp.json server entry: local (stdio) or remote (HTTP / SSE), with a raw JSON mode */
const McpServerConfigEditor = ({ serverName, initialConfig, existingNames = [], onSubmit, onCancel }: McpServerConfigEditorProps) => {
  const isNew = serverName === undefined
  const [state, setState] = React.useState<EditorState>(() => stateFromConfig(serverName || '', initialConfig || { command: '' }))
  const [showErrors, setShowErrors] = React.useState(false)
  const [mode, setMode] = React.useState<'form' | 'json'>('form')
  const [jsonText, setJsonText] = React.useState('')
  const [jsonError, setJsonError] = React.useState<string | null>(null)
  const [submitting, setSubmitting] = React.useState(false)
  const [submitError, setSubmitError] = React.useState<string | null>(null)
  const [advancedOpen, setAdvancedOpen] = React.useState(() => !!(initialConfig?.cwd || initialConfig?.timeout || initialConfig?.legacy))

  const takenNames = React.useMemo(() => existingNames.filter((n) => n !== serverName), [existingNames, serverName])
  const errors = React.useMemo(() => validate(state, takenNames), [state, takenNames])
  const visibleErrors: Errors = showErrors ? errors : {}
  const set = <K extends keyof EditorState>(key: K, value: EditorState[K]) => setState((s) => ({ ...s, [key]: value }))

  const toJson = (s: EditorState) => JSON.stringify({ [s.name.trim() || 'my-server']: configFromState(s) }, null, 2)

  const switchMode = (next: 'form' | 'json') => {
    if (next === mode) return
    if (next === 'json') {
      setJsonText(toJson(state))
      setJsonError(null)
    } else if (jsonError) {
      return
    }
    setMode(next)
  }

  const onJsonChange = (text: string) => {
    setJsonText(text)
    try {
      const parsed = JSON.parse(text)
      const entries = Object.entries(parsed?.mcpServers ?? parsed ?? {})
      if (typeof parsed !== 'object' || Array.isArray(parsed) || entries.length !== 1) {
        throw new Error('Expected an object with exactly one server: { "<name>": { ... } }')
      }
      const [name, config] = entries[0]
      if (typeof config !== 'object' || config === null || Array.isArray(config)) throw new Error(`"${name}" must be an object.`)
      setState(stateFromConfig(name, config as McpServerConfig))
      setJsonError(null)
    } catch (e: any) {
      setJsonError(e?.message || String(e))
    }
  }

  const applyPreset = (preset: typeof STDIO_PRESETS[number]) => setState((s) => ({
    ...s, command: preset.command, args: preset.args.map((value) => ({ id: rowId(), value })),
  }))

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setShowErrors(true)
    setSubmitError(null)
    if (jsonError || Object.keys(errors).length > 0) return
    setSubmitting(true)
    try {
      await onSubmit(state.name.trim(), configFromState(state))
    } catch (err: any) {
      setSubmitError(err?.message || String(err))
    } finally {
      setSubmitting(false)
    }
  }

  const commandLine = [state.command.trim(), ...state.args.map((a) => a.value).filter(Boolean)].filter(Boolean).map(quoteArg).join(' ')

  return (
    <form className="flex min-h-0 flex-1 flex-col" onSubmit={handleSubmit} noValidate>
      <div className="flex min-h-0 flex-1 flex-col gap-6 overflow-y-auto px-4 pb-4">
        <div className="flex justify-end">
          <div className="inline-flex rounded-md border p-0.5">
            <Button type="button" size="sm" variant={mode === 'form' ? 'secondary' : 'ghost'} onClick={() => switchMode('form')}
                    disabled={mode === 'json' && !!jsonError} title={jsonError ? 'Fix the JSON first' : undefined}>
              <ListIcon /> Form
            </Button>
            <Button type="button" size="sm" variant={mode === 'json' ? 'secondary' : 'ghost'} onClick={() => switchMode('json')}>
              <BracesIcon /> JSON
            </Button>
          </div>
        </div>

        {mode === 'json' ? (
          <Field label="mcp.json entry" htmlFor="mcp-json" error={jsonError || undefined}
                 hint={<>One server, as it appears under <code className="font-mono">mcpServers</code>. A whole <code className="font-mono">{'{"mcpServers": …}'}</code> with one server works too.</>}>
            <Textarea id="mcp-json" className="min-h-80 font-mono text-xs" spellCheck={false} value={jsonText}
                      onChange={(e) => onJsonChange(e.target.value)} />
          </Field>
        ) : (
          <>
            <section className="flex flex-col gap-4">
              <Field label="Name" htmlFor="mcp-name" error={visibleErrors.name}
                     hint={<>Tools are named <code className="font-mono">mcp__{state.name.trim() || '<name>'}__&lt;tool&gt;</code>.</>}>
                <Input id="mcp-name" className="font-mono" value={state.name} placeholder="my-server" autoFocus={isNew}
                       disabled={!isNew} aria-invalid={!!visibleErrors.name}
                       onChange={(e) => set('name', e.target.value)} />
              </Field>
              <Field label="Description" htmlFor="mcp-description" hint="Optional.">
                <Input id="mcp-description" value={state.description} placeholder="What this server is for"
                       onChange={(e) => set('description', e.target.value)} />
              </Field>
            </section>

            <section className="flex flex-col gap-2">
              <Label>Transport</Label>
              <Segmented value={state.transport === 'stdio' ? 'stdio' : 'remote'}
                         onChange={(v) => set('transport', v === 'stdio' ? 'stdio' : (state.transport === 'sse' ? 'sse' : 'http'))}
                         options={[
                           { value: 'stdio', label: 'Local (stdio)', description: 'Start a process and talk over stdin/stdout', icon: <TerminalIcon size={16} /> },
                           { value: 'remote', label: 'Remote', description: 'Connect to a server over HTTP', icon: <GlobeIcon size={16} /> },
                         ]} />
            </section>

            {state.transport === 'stdio' ? (
              <section className="flex flex-col gap-4">
                <Field label="Command" htmlFor="mcp-command" error={visibleErrors.command}
                       hint="Paste a whole command line to split it into command and arguments.">
                  <Input id="mcp-command" className="font-mono" value={state.command} placeholder="docker"
                         aria-invalid={!!visibleErrors.command}
                         onChange={(e) => set('command', e.target.value)}
                         onPaste={(e) => {
                           const words = splitCommandLine(e.clipboardData.getData('text'))
                           if (words.length > 1 && state.command === '') {
                             e.preventDefault()
                             setState((s) => ({ ...s, command: words[0], args: words.slice(1).map((value) => ({ id: rowId(), value })) }))
                           }
                         }} />
                  {!state.command && state.args.length === 0 && (
                    <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
                      Start from:
                      {STDIO_PRESETS.map((p) => (
                        <Button key={p.label} type="button" size="sm" variant="outline" className="h-6 px-2 text-xs" onClick={() => applyPreset(p)}>
                          {p.label}
                        </Button>
                      ))}
                    </div>
                  )}
                </Field>
                <Field label="Arguments" hint="Press Enter to add the next argument.">
                  <ArgsEditor args={state.args} onChange={(args) => set('args', args)} />
                </Field>
                {commandLine && (
                  <pre className="overflow-x-auto rounded-md border bg-muted px-3 py-2 font-mono text-xs"><span className="select-none text-muted-foreground">$ </span>{commandLine}</pre>
                )}
                <Field label="Environment variables" error={visibleErrors.env}
                       hint="Paste KEY=value lines, for example from a .env file, to add several at once.">
                  <KeyValueEditor rows={state.env} onChange={(env) => set('env', env)}
                                  keyPlaceholder="API_KEY" valuePlaceholder="value" addLabel="Add variable" />
                </Field>
              </section>
            ) : (
              <section className="flex flex-col gap-4">
                <Field label="URL" htmlFor="mcp-url" error={visibleErrors.url}>
                  <Input id="mcp-url" className="font-mono" type="url" value={state.url} placeholder="https://example.com/mcp"
                         aria-invalid={!!visibleErrors.url}
                         onChange={(e) => set('url', e.target.value)} />
                </Field>
                <div className="flex flex-col gap-2">
                  <Label>Protocol</Label>
                  <Segmented value={state.transport} onChange={(v) => set('transport', v)}
                             options={[
                               { value: 'http', label: 'Streamable HTTP', description: 'Current MCP transport' },
                               { value: 'sse', label: 'SSE', description: 'Older servers using Server-Sent Events' },
                             ]} />
                </div>
                <Field label="Headers" error={visibleErrors.headers} hint="Sent with every request, for example for authentication.">
                  <KeyValueEditor rows={state.headers} onChange={(headers) => set('headers', headers)}
                                  keyPlaceholder="X-Api-Key" valuePlaceholder="value" addLabel="Add header" />
                  {!state.headers.some((h) => h.key.toLowerCase() === 'authorization') && (
                    <Button type="button" size="sm" variant="ghost" className="self-start"
                            onClick={() => set('headers', [...state.headers, { id: rowId(), key: 'Authorization', value: 'Bearer ' }])}>
                      <KeyRoundIcon /> Add bearer token
                    </Button>
                  )}
                </Field>
              </section>
            )}

            <Collapsible open={advancedOpen} onOpenChange={setAdvancedOpen}>
              <CollapsibleTrigger className="flex cursor-pointer items-center gap-1 text-sm font-medium">
                <ChevronRightIcon size={16} className={cn('transition-transform', advancedOpen && 'rotate-90')} /> Advanced
              </CollapsibleTrigger>
              <CollapsibleContent className="flex flex-col gap-4 pt-4">
                {state.transport === 'stdio' && (
                  <Field label="Working directory" htmlFor="mcp-cwd" hint="Directory the command runs in. Optional.">
                    <Input id="mcp-cwd" className="font-mono" value={state.cwd} placeholder="/path/to/project"
                           onChange={(e) => set('cwd', e.target.value)} />
                  </Field>
                )}
                <Field label="Timeout (ms)" htmlFor="mcp-timeout" error={visibleErrors.timeout}
                       hint="Maximum time to wait for a response. Empty uses the default.">
                  <Input id="mcp-timeout" type="number" min={1} step={1} className="w-40" value={state.timeout} placeholder="30000"
                         aria-invalid={!!visibleErrors.timeout}
                         onChange={(e) => set('timeout', e.target.value)} />
                </Field>
                <label className="flex cursor-pointer items-start gap-2 text-sm">
                  <input type="checkbox" className="mt-0.5 size-4 accent-primary" checked={state.legacy}
                         onChange={(e) => set('legacy', e.target.checked)} />
                  <span>
                    <span className="block font-medium">Legacy protocol</span>
                    <span className="block text-xs text-muted-foreground">For servers that only support an older MCP protocol version.</span>
                  </span>
                </label>
                {Object.keys(state.extra).length > 0 && (
                  <p className="text-xs text-muted-foreground">
                    Other settings kept as they are: {Object.keys(state.extra).map((k) => <code key={k} className="mr-1 font-mono">{k}</code>)}
                    (edit them in JSON mode).
                  </p>
                )}
              </CollapsibleContent>
            </Collapsible>
          </>
        )}
      </div>

      <div className="flex flex-col gap-2 border-t p-4">
        {showErrors && Object.keys(errors).length > 0 && mode === 'json' && (
          <p className="text-sm text-destructive">{Object.values(errors).join(' ')}</p>
        )}
        {submitError && (
          <div className="rounded-md border border-destructive/50 p-3 text-sm text-destructive">{submitError}</div>
        )}
        <div className="flex justify-end gap-2">
          {onCancel && <Button type="button" variant="ghost" onClick={onCancel} disabled={submitting}>Cancel</Button>}
          <Button type="submit" disabled={submitting || !!jsonError}>
            {submitting ? <LoaderIcon className="animate-spin" /> : <SaveIcon />}
            {isNew ? 'Add server' : 'Save changes'}
          </Button>
        </div>
      </div>
    </form>
  )
}

export default McpServerConfigEditor
