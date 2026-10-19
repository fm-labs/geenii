import React from 'react'
import {
  AlertTriangleIcon, BotIcon, BrainIcon, CheckIcon, ChevronsUpDownIcon, CopyIcon, FileTextIcon, FolderIcon,
  LoaderIcon, PlugIcon, PlusIcon, SaveIcon, ScrollTextIcon, SearchIcon, SettingsIcon, SparklesIcon, TerminalIcon,
  Trash2Icon, WrenchIcon, XIcon,
} from 'lucide-react'
import { AgentDetailType, mcpServerOfTool, shortToolName } from '@/app/agents/agent-types.ts'
import { ToolType } from '@/app/tools/tool-types.ts'
import { AiModelInfo } from '@/api/xai.types.ts'
import { OutputDataMarkdown } from '@/components/output-data-markdown.tsx'
import { markdownClass } from '@/components/xchat/parts/media-parts.tsx'
import { Badge } from '@/components/ui/badge.tsx'
import { Button } from '@/components/ui/button.tsx'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.tsx'
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from '@/components/ui/command.tsx'
import { Input } from '@/components/ui/input.tsx'
import { Label } from '@/components/ui/label.tsx'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover.tsx'
import { Skeleton } from '@/components/ui/skeleton.tsx'
import { Textarea } from '@/components/ui/textarea.tsx'
import { useApi } from '@/context/api-context.tsx'
import { modelId, useModels } from '@/hooks/use-models.ts'
import { cn } from 'cn'

/* ---------- types ---------- */

type Scope = 'user' | 'project' | 'global'

/** The frontmatter of an agent spec file (AgentSpec without the fields set at load time) */
export type AgentSpecInput = {
  name: string
  label?: string
  description?: string
  model: string
  class_name?: string
  system?: string
  model_parameters?: Record<string, any>
  mcp_servers?: string[]
  tools?: string[]
  skills?: string[]
  working_dir?: string
  allowed_dirs?: string[]
}

export type AgentConfigSubmit = {
  spec: AgentSpecInput
  /** Markdown body of the spec file */
  instructions: string
  /** Agent directory to write to; the registry sets `scope` from it */
  scope: Scope
  /** The complete spec file: YAML frontmatter plus instructions */
  markdown: string
}

/** GET /api/v1/skills/ (only the fields used here) */
type SkillOption = { name: string, description: string }
type ParamRow = { id: string, key: string, value: string }

type EditorState = {
  name: string
  label: string
  description: string
  model: string
  className: string
  scope: Scope
  system: string
  instructions: string
  params: ParamRow[]
  mcpServers: string[]
  tools: string[]
  skills: string[]
  workingDir: string
  allowedDirs: string
}

type TabId = 'general' | 'model' | 'tools' | 'skills' | 'instructions' | 'preview'
type Errors = Partial<Record<'name' | 'model' | 'params' | 'className', string>>

/* ---------- constants & helpers ---------- */

const NAME_PATTERN = /^[A-Za-z0-9_-]+$/
const DEFAULT_CLASS = 'geenii.agents.Agent'
const AGENT_CLASSES = [
  { value: '', label: 'Agent', description: 'The standard agent (default)' },
  { value: 'geenii.agents.RoutingAgent', label: 'RoutingAgent', description: 'Hands each request to the best-suited agent' },
  { value: 'geenii.agents.ProcessManagerAgent', label: 'ProcessManagerAgent', description: 'Manages background processes' },
]
const SCOPES: { value: Scope, label: string, path: string }[] = [
  { value: 'user', label: 'User', path: '~/.geenii/agents' },
  { value: 'project', label: 'Project', path: '<working dir>/.geenii/agents' },
  { value: 'global', label: 'Global', path: '/var/geenii/agents' },
]
const KNOWN_PARAMS: { key: string, hint: string, defaultValue: string, min?: number, max?: number, integer?: boolean }[] = [
  { key: 'temperature', hint: 'Randomness, 0–2', defaultValue: '0.7', min: 0, max: 2 },
  { key: 'top_p', hint: 'Nucleus sampling, 0–1', defaultValue: '1', min: 0, max: 1 },
  { key: 'max_tokens', hint: 'Maximum output tokens', defaultValue: '4096', min: 1, integer: true },
]

let rowCounter = 0
const rowId = () => `p-${++rowCounter}`

/** Parses a parameter value typed as text: numbers, booleans, null and JSON objects/arrays keep their type */
const parseParamValue = (raw: string): any => {
  const v = raw.trim()
  if (v === '') return ''
  if (/^-?\d+(\.\d+)?([eE][-+]?\d+)?$/.test(v)) return Number(v)
  if (v === 'true' || v === 'false') return v === 'true'
  if (v === 'null') return null
  if (/^[[{"]/.test(v)) return JSON.parse(v)
  return v
}

const formatParamValue = (value: any) => (typeof value === 'string' ? value : JSON.stringify(value))

const stateFromAgent = (agent?: AgentDetailType | null): EditorState => ({
  name: agent?.name || '',
  label: agent?.label || '',
  description: agent?.description?.trim() || '',
  model: agent?.model || '',
  className: agent?.class_name && agent.class_name !== DEFAULT_CLASS ? agent.class_name : '',
  scope: agent?.scope || 'user',
  system: agent?.system || '',
  instructions: agent?.instructions?.trim() || '',
  params: Object.entries(agent?.model_parameters || {}).map(([key, value]) => ({ id: rowId(), key, value: formatParamValue(value) })),
  mcpServers: [...(agent?.mcp_servers || [])],
  tools: [...(agent?.tools || [])],
  skills: [...(agent?.skills || [])],
  workingDir: agent?.working_dir || '',
  allowedDirs: (agent?.allowed_dirs || []).join('\n'),
})

const specFromState = (s: EditorState): AgentSpecInput => {
  const spec: AgentSpecInput = { name: s.name.trim(), model: s.model.trim() }
  if (s.label.trim()) spec.label = s.label.trim()
  if (s.description.trim()) spec.description = s.description.trim()
  if (s.className.trim()) spec.class_name = s.className.trim()
  if (s.system.trim()) spec.system = s.system.trim()
  const params = s.params.filter((p) => p.key.trim())
  if (params.length > 0) {
    spec.model_parameters = Object.fromEntries(params.map((p) => {
      try {
        return [p.key.trim(), parseParamValue(p.value)]
      } catch {
        return [p.key.trim(), p.value]
      }
    }))
  }
  if (s.mcpServers.length > 0) spec.mcp_servers = s.mcpServers
  if (s.tools.length > 0) spec.tools = s.tools
  if (s.skills.length > 0) spec.skills = s.skills
  if (s.scope === 'project') {
    if (s.workingDir.trim()) spec.working_dir = s.workingDir.trim()
    const dirs = s.allowedDirs.split('\n').map((d) => d.trim()).filter(Boolean)
    if (dirs.length > 0) spec.allowed_dirs = dirs
  }
  return spec
}

const validate = (s: EditorState, takenNames: string[]): Errors => {
  const errors: Errors = {}
  const name = s.name.trim()
  if (!name) errors.name = 'A name is required.'
  else if (!NAME_PATTERN.test(name)) errors.name = 'Use letters, digits, - and _ only.'
  else if (takenNames.includes(name)) errors.name = `An agent named "${name}" already exists.`
  if (!s.model.trim()) errors.model = 'Choose a model.'
  else if (!s.model.includes(':')) errors.model = 'Use the form provider:model, for example ollama:qwen3:8b.'
  if (s.className.trim() && !/^[A-Za-z_][\w]*(\.[A-Za-z_][\w]*)+$/.test(s.className.trim())) {
    errors.className = 'Use a full Python path, for example mypackage.agents.MyAgent.'
  }

  const keys = s.params.map((p) => p.key.trim()).filter(Boolean)
  if (new Set(keys).size !== keys.length) errors.params = 'Parameter names must be unique.'
  else if (s.params.some((p) => !p.key.trim() && p.value.trim())) errors.params = 'Every parameter needs a name.'
  else {
    for (const p of s.params) {
      let value: any
      try {
        value = parseParamValue(p.value)
      } catch {
        errors.params = `"${p.key}" is not valid JSON.`
        break
      }
      const known = KNOWN_PARAMS.find((k) => k.key === p.key.trim())
      if (known && p.value.trim()) {
        if (typeof value !== 'number' || (known.integer && !Number.isInteger(value))
          || (known.min !== undefined && value < known.min) || (known.max !== undefined && value > known.max)) {
          errors.params = `${known.key}: ${known.hint.toLowerCase()}${known.integer ? ', whole number' : ''}.`
          break
        }
      }
    }
  }
  return errors
}

/* --- minimal YAML for the preview: scalars, lists of scalars and maps; nested values as JSON flow --- */

const yamlScalar = (value: any): string => {
  if (value === null || value === undefined) return 'null'
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  if (typeof value === 'object') return JSON.stringify(value)
  const s = String(value)
  const needsQuotes = s === '' || /^\s|\s$/.test(s) || /^[-?:,[\]{}#&*!|>'"%@`]/.test(s) || /: | #/.test(s)
    || /^(true|false|yes|no|on|off|null|~)$/i.test(s) || /^[-+]?(\d[\d_]*)?\.?\d+([eE][-+]?\d+)?$/.test(s)
  return needsQuotes ? JSON.stringify(s) : s
}

const yamlEntry = (key: string, value: any): string => {
  if (Array.isArray(value)) return `${key}:\n${value.map((v) => `  - ${yamlScalar(v)}`).join('\n')}`
  if (value && typeof value === 'object') {
    return `${key}:\n${Object.entries(value).map(([k, v]) => `  ${yamlScalar(k)}: ${yamlScalar(v)}`).join('\n')}`
  }
  if (typeof value === 'string' && value.includes('\n')) {
    return `${key}: |-\n${value.split('\n').map((l) => (l ? `  ${l}` : '')).join('\n')}`
  }
  return `${key}: ${yamlScalar(value)}`
}

export const agentMarkdown = (spec: AgentSpecInput, instructions: string) => {
  const order: (keyof AgentSpecInput)[] = ['name', 'label', 'description', 'model', 'class_name', 'model_parameters',
    'mcp_servers', 'tools', 'skills', 'working_dir', 'allowed_dirs', 'system']
  const front = order.filter((k) => spec[k] !== undefined).map((k) => yamlEntry(k, spec[k])).join('\n')
  return `---\n${front}\n---\n${instructions.trim() ? `\n${instructions.trim()}\n` : ''}`
}

/* ---------- building blocks ---------- */

const Field = ({ label, htmlFor, hint, error, children, className }: {
  label: React.ReactNode, htmlFor?: string, hint?: React.ReactNode, error?: string, children: React.ReactNode, className?: string
}) => (
  <div className={cn('flex flex-col gap-1.5', className)}>
    <Label htmlFor={htmlFor}>{label}</Label>
    {children}
    {error
      ? <p className="text-xs text-destructive">{error}</p>
      : hint && <p className="text-xs text-muted-foreground">{hint}</p>}
  </div>
)

const Check = ({ checked, onChange, children, className, disabled, title }: {
  checked: boolean, onChange: (checked: boolean) => void, children: React.ReactNode, className?: string, disabled?: boolean, title?: string
}) => (
  <label title={title} className={cn('flex cursor-pointer items-start gap-2.5 rounded-md border px-3 py-2 text-sm transition-colors hover:bg-muted/50',
    checked && 'border-primary/60 bg-muted/60', disabled && 'cursor-not-allowed opacity-60', className)}>
    <input type="checkbox" className="mt-0.5 size-4 shrink-0 accent-primary" checked={checked} disabled={disabled}
           onChange={(e) => onChange(e.target.checked)} />
    <span className="min-w-0 flex-1">{children}</span>
  </label>
)

const SearchInput = ({ value, onChange, placeholder }: { value: string, onChange: (v: string) => void, placeholder: string }) => (
  <div className="relative">
    <SearchIcon size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
    <Input className="h-8 pl-8" placeholder={placeholder} value={value} onChange={(e) => onChange(e.target.value)} />
  </div>
)

const Missing = ({ children }: { children: React.ReactNode }) => (
  <span className="flex items-center gap-1 text-xs text-amber-600 dark:text-amber-400">
    <AlertTriangleIcon size={12} className="shrink-0" /> {children}
  </span>
)

/** Model picker: the server's models grouped by provider, or any typed "provider:model" id */
const ModelCombobox = ({ value, onChange, invalid }: { value: string, onChange: (v: string) => void, invalid?: boolean }) => {
  const { models, loading, error } = useModels()
  const [open, setOpen] = React.useState(false)
  const [query, setQuery] = React.useState('')

  const byProvider = React.useMemo(() => {
    const groups: Record<string, AiModelInfo[]> = {}
    models.forEach((m) => { (groups[m.provider] ||= []).push(m) })
    return Object.entries(groups).sort(([a], [b]) => a.localeCompare(b))
  }, [models])
  const current = models.find((m) => modelId(m) === value)
  const typed = query.trim()

  return (
    <Popover open={open} onOpenChange={(o) => { setOpen(o); if (!o) setQuery('') }}>
      <PopoverTrigger asChild>
        <Button type="button" variant="outline" role="combobox" aria-expanded={open} aria-invalid={invalid}
                className={cn('w-full justify-between font-mono font-normal', !value && 'text-muted-foreground', invalid && 'border-destructive')}>
          <span className="flex min-w-0 items-center gap-2">
            <BrainIcon className="shrink-0" />
            <span className="truncate">{value || 'Choose a model …'}</span>
          </span>
          <span className="flex shrink-0 items-center gap-1.5">
            {current && <Badge variant="outline" className="font-sans">{current.locality}</Badge>}
            {value && !current && !loading && <Badge variant="outline" className="font-sans">custom</Badge>}
            <ChevronsUpDownIcon className="opacity-50" />
          </span>
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-(--radix-popover-trigger-width) p-0" align="start">
        <Command>
          <CommandInput placeholder="Search models or type provider:model …" value={query} onValueChange={setQuery} />
          <CommandList className="max-h-72">
            {loading && <div className="p-3 text-sm text-muted-foreground">Loading models …</div>}
            {error && <div className="p-3 text-sm text-destructive">Could not load models: {error}</div>}
            <CommandEmpty>{typed.includes(':') ? null : 'No model found. Type provider:model to use any model.'}</CommandEmpty>
            {typed.includes(':') && !models.some((m) => modelId(m) === typed) && (
              <CommandGroup heading="Custom">
                <CommandItem value={`custom ${typed}`} onSelect={() => { onChange(typed); setOpen(false) }}>
                  <PlusIcon /> Use <span className="font-mono">{typed}</span>
                </CommandItem>
              </CommandGroup>
            )}
            {byProvider.map(([provider, list]) => (
              <CommandGroup key={provider} heading={provider}>
                {list.map((m) => {
                  const id = modelId(m)
                  return (
                    <CommandItem key={id} value={`${id} ${m.description || ''}`} onSelect={() => { onChange(id); setOpen(false) }}>
                      <CheckIcon className={cn(id === value ? 'opacity-100' : 'opacity-0')} />
                      <span className="truncate font-mono">{m.name}</span>
                      <span className="ml-auto flex shrink-0 items-center gap-1">
                        {m.capabilities?.includes('tools') && <WrenchIcon className="size-3 text-muted-foreground" aria-label="supports tools" />}
                        {!m.installed && m.locality === 'local' && <Badge variant="outline" className="text-[10px]">not installed</Badge>}
                      </span>
                    </CommandItem>
                  )
                })}
              </CommandGroup>
            ))}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}

/* ---------- editor ---------- */

export type AgentConfigEditorProps = {
  /** Name of the agent to edit; omit to create a new agent */
  agentName?: string
  /** Names already in use, to reject duplicates */
  existingNames?: string[]
  /** Called with the new spec; a thrown error is shown in the editor */
  onSubmit: (result: AgentConfigSubmit) => Promise<void> | void
  onCancel: () => void
}

/** Create or edit an agent spec: identity, model, MCP servers & tools, skills and instructions, with a file preview */
const AgentConfigEditor = ({ agentName, existingNames = [], onSubmit, onCancel }: AgentConfigEditorProps) => {
  const isNew = agentName === undefined
  const { fetchJson } = useApi()

  const [agent, setAgent] = React.useState<AgentDetailType | null>(null)
  const [state, setState] = React.useState<EditorState>(() => stateFromAgent(null))
  const [loadingAgent, setLoadingAgent] = React.useState(!isNew)
  const [loadError, setLoadError] = React.useState<string | null>(null)

  const [tools, setTools] = React.useState<ToolType[]>([])
  const [skills, setSkills] = React.useState<SkillOption[]>([])
  const [servers, setServers] = React.useState<McpServer[]>([])
  const [catalogLoading, setCatalogLoading] = React.useState(true)
  const [catalogErrors, setCatalogErrors] = React.useState<string[]>([])

  const [tab, setTab] = React.useState<TabId>('general')
  const [showErrors, setShowErrors] = React.useState(false)
  const [submitting, setSubmitting] = React.useState(false)
  const [submitError, setSubmitError] = React.useState<string | null>(null)
  const [toolFilter, setToolFilter] = React.useState('')
  const [skillFilter, setSkillFilter] = React.useState('')
  const [instructionsPreview, setInstructionsPreview] = React.useState(false)
  const [copied, setCopied] = React.useState(false)

  // the agent being edited, with its instructions
  React.useEffect(() => {
    if (isNew) return
    let cancelled = false
    ;(fetchJson(`/api/v1/agents/${encodeURIComponent(agentName)}`) as Promise<AgentDetailType>)
      .then((data) => {
        if (cancelled) return
        setAgent(data)
        setState(stateFromAgent(data))
      })
      .catch((err) => { if (!cancelled) setLoadError(err?.message || 'Unknown error') })
      .finally(() => { if (!cancelled) setLoadingAgent(false) })
    return () => { cancelled = true }
  }, [fetchJson, agentName, isNew])

  // what can be assigned: tools (including MCP tools), skills and MCP servers
  React.useEffect(() => {
    let cancelled = false
    Promise.allSettled([
      fetchJson('/api/v1/tools/') as Promise<ToolType[]>,
      fetchJson('/api/v1/skills/') as Promise<SkillOption[]>,
      fetchJson('/api/v1/mcp/servers') as Promise<McpServer[]>,
    ]).then(([t, sk, sv]) => {
      if (cancelled) return
      const errs: string[] = []
      if (t.status === 'fulfilled') setTools([...t.value].sort((a, b) => a.name.localeCompare(b.name)))
      else errs.push(`tools: ${t.reason?.message || 'unknown error'}`)
      if (sk.status === 'fulfilled') setSkills([...sk.value].sort((a, b) => a.name.localeCompare(b.name)))
      else errs.push(`skills: ${sk.reason?.message || 'unknown error'}`)
      if (sv.status === 'fulfilled') setServers([...sv.value].sort((a, b) => a.name.localeCompare(b.name)))
      else errs.push(`MCP servers: ${sv.reason?.message || 'unknown error'}`)
      setCatalogErrors(errs)
      setCatalogLoading(false)
    })
    return () => { cancelled = true }
  }, [fetchJson])

  const takenNames = React.useMemo(() => existingNames.filter((n) => n !== agentName), [existingNames, agentName])
  const errors = React.useMemo(() => validate(state, takenNames), [state, takenNames])
  const visibleErrors: Errors = showErrors ? errors : {}
  const set = <K extends keyof EditorState>(key: K, value: EditorState[K]) => setState((s) => ({ ...s, [key]: value }))
  const spec = React.useMemo(() => specFromState(state), [state])
  const markdown = React.useMemo(() => agentMarkdown(spec, state.instructions), [spec, state.instructions])

  /* --- tools, grouped: built-in, then one group per assigned MCP server --- */
  const toolGroups = React.useMemo(() => {
    const builtin: ToolType[] = []
    const byServer: Record<string, ToolType[]> = {}
    tools.forEach((t) => {
      const server = mcpServerOfTool(t.name)
      if (server) (byServer[server] ||= []).push(t)
      else builtin.push(t)
    })
    return { builtin, byServer }
  }, [tools])
  const knownToolNames = React.useMemo(() => new Set(tools.map((t) => t.name)), [tools])
  const unknownTools = catalogLoading ? [] : state.tools.filter((t) => !knownToolNames.has(t))
  const toolMatches = (t: ToolType) => {
    const q = toolFilter.trim().toLowerCase()
    return !q || t.name.toLowerCase().includes(q) || (t.description || '').toLowerCase().includes(q)
  }

  const toggleTool = (name: string, on: boolean) =>
    set('tools', on ? [...state.tools, name] : state.tools.filter((t) => t !== name))
  const setGroupTools = (names: string[], on: boolean) => setState((s) => ({
    ...s, tools: on ? [...new Set([...s.tools, ...names])] : s.tools.filter((t) => !names.includes(t)),
  }))
  const toggleServer = (name: string, on: boolean) => setState((s) => ({
    ...s,
    mcpServers: on ? [...s.mcpServers, name] : s.mcpServers.filter((n) => n !== name),
    // a removed server's tools can't be called any more
    tools: on ? s.tools : s.tools.filter((t) => mcpServerOfTool(t) !== name),
  }))

  const knownServerNames = new Set(servers.map((s) => s.name))
  const unknownServers = catalogLoading ? [] : state.mcpServers.filter((s) => !knownServerNames.has(s))
  const knownSkillNames = new Set(skills.map((s) => s.name))
  const unknownSkills = catalogLoading ? [] : state.skills.filter((s) => !knownSkillNames.has(s))
  const filteredSkills = skills.filter((s) => {
    const q = skillFilter.trim().toLowerCase()
    return !q || s.name.toLowerCase().includes(q) || (s.description || '').toLowerCase().includes(q)
  })

  /* --- tabs, with an error dot on tabs that have invalid fields --- */
  const tabErrors: Partial<Record<TabId, boolean>> = showErrors ? {
    general: !!(errors.name || errors.className),
    model: !!(errors.model || errors.params),
  } : {}
  const tabs: { id: TabId, label: string, icon: React.ElementType, count?: number }[] = [
    { id: 'general', label: 'General', icon: SettingsIcon },
    { id: 'model', label: 'Model', icon: BrainIcon },
    { id: 'tools', label: 'MCP & Tools', icon: WrenchIcon, count: state.tools.length },
    { id: 'skills', label: 'Skills', icon: SparklesIcon, count: state.skills.length },
    { id: 'instructions', label: 'Instructions', icon: ScrollTextIcon },
    { id: 'preview', label: 'Preview', icon: FileTextIcon },
  ]

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setShowErrors(true)
    setSubmitError(null)
    if (Object.keys(errors).length > 0) {
      setTab(errors.name || errors.className ? 'general' : 'model')
      return
    }
    setSubmitting(true)
    try {
      await onSubmit({ spec, instructions: state.instructions.trim(), scope: state.scope, markdown })
    } catch (err: any) {
      setSubmitError(err?.message || String(err))
    } finally {
      setSubmitting(false)
    }
  }

  const copyMarkdown = () => {
    navigator.clipboard?.writeText(markdown).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }

  const usedParamKeys = new Set(state.params.map((p) => p.key.trim()))

  return (
    <Card className="gap-0 py-0">
      <form onSubmit={handleSubmit} noValidate className="flex flex-col">
        <CardHeader className="gap-1 border-b py-4">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <CardTitle className="flex items-center gap-2">
                <BotIcon size={16} className="shrink-0" />
                <span className="truncate">{isNew ? 'New agent' : `Edit ${agent?.label || agentName}`}</span>
              </CardTitle>
              <CardDescription className="mt-1">
                {isNew
                  ? 'Define who the agent is, which model it runs on and what it may use.'
                  : agent?.file_path
                    ? <span className="font-mono text-xs break-all">{agent.file_path}</span>
                    : 'Built-in agent without a spec file. Saving creates one that replaces it.'}
              </CardDescription>
            </div>
            <Button type="button" size="icon" variant="ghost" onClick={onCancel} title="Close editor">
              <XIcon />
            </Button>
          </div>
          <div role="tablist" className="-mb-4 mt-2 flex gap-1 overflow-x-auto">
            {tabs.map(({ id, label, icon: Icon, count }) => (
              <button key={id} type="button" role="tab" aria-selected={tab === id} onClick={() => setTab(id)}
                      className={cn('relative flex shrink-0 cursor-pointer items-center gap-1.5 border-b-2 px-2.5 pb-2.5 pt-1 text-sm transition-colors',
                        tab === id ? 'border-primary font-medium text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground')}>
                <Icon size={14} /> {label}
                {count !== undefined && count > 0 && <Badge variant="secondary" className="h-4 px-1.5 text-[10px]">{count}</Badge>}
                {tabErrors[id] && <span className="size-1.5 rounded-full bg-destructive" aria-label="has errors" />}
              </button>
            ))}
          </div>
        </CardHeader>

        <CardContent className="flex flex-col gap-5 py-5">
          {loadError && (
            <div className="rounded-lg border border-destructive/50 p-3 text-sm text-destructive">Failed to load the agent: {loadError}</div>
          )}
          {catalogErrors.length > 0 && (
            <div className="rounded-lg border border-amber-500/50 p-3 text-xs text-amber-700 dark:text-amber-400">
              Some choices could not be loaded ({catalogErrors.join('; ')}). Assigned items are kept.
            </div>
          )}

          {loadingAgent ? (
            <div className="flex flex-col gap-3">
              <Skeleton className="h-9 w-full" /><Skeleton className="h-9 w-full" /><Skeleton className="h-24 w-full" />
            </div>
          ) : (
            <>
              {tab === 'general' && (
                <div className="flex flex-col gap-4">
                  <div className="grid gap-4 sm:grid-cols-2">
                    <Field label="Name" htmlFor="agent-name" error={visibleErrors.name}
                           hint={isNew ? 'Used in URLs and to address the agent. Can\'t be changed later.' : 'The name can\'t be changed.'}>
                      <Input id="agent-name" className="font-mono" value={state.name} placeholder="my-agent" autoFocus={isNew}
                             disabled={!isNew} aria-invalid={!!visibleErrors.name} onChange={(e) => set('name', e.target.value)} />
                    </Field>
                    <Field label="Label" htmlFor="agent-label" hint="Display name. Optional.">
                      <Input id="agent-label" value={state.label} placeholder="My Agent" onChange={(e) => set('label', e.target.value)} />
                    </Field>
                  </div>
                  <Field label="Description" htmlFor="agent-description"
                         hint={<>What the agent is for and when to use it. The routing agent reads this to pick an agent. <span className="tabular-nums">{state.description.length}</span> characters.</>}>
                    <Textarea id="agent-description" className="min-h-20" value={state.description}
                              placeholder="Summarizes tech news. Use for questions like …" onChange={(e) => set('description', e.target.value)} />
                  </Field>

                  <div className="flex flex-col gap-2">
                    <Label>Agent class</Label>
                    <div className="grid gap-2 sm:grid-cols-3">
                      {AGENT_CLASSES.map((c) => (
                        <button key={c.value} type="button" role="radio" aria-checked={state.className === c.value}
                                onClick={() => set('className', c.value)}
                                className={cn('flex cursor-pointer flex-col items-start rounded-md border px-3 py-2 text-left text-sm hover:bg-muted/50',
                                  state.className === c.value && 'border-primary bg-muted ring-1 ring-primary')}>
                          <span className="font-medium">{c.label}</span>
                          <span className="text-xs text-muted-foreground">{c.description}</span>
                        </button>
                      ))}
                    </div>
                    <Input className="font-mono" placeholder="or a custom class, e.g. mypackage.agents.MyAgent"
                           value={AGENT_CLASSES.some((c) => c.value === state.className) ? '' : state.className}
                           aria-invalid={!!visibleErrors.className}
                           onChange={(e) => set('className', e.target.value)} />
                    {visibleErrors.className && <p className="text-xs text-destructive">{visibleErrors.className}</p>}
                  </div>

                  <div className="flex flex-col gap-2">
                    <Label>Location</Label>
                    <div className="grid gap-2 sm:grid-cols-3">
                      {SCOPES.map((sc) => (
                        <button key={sc.value} type="button" role="radio" aria-checked={state.scope === sc.value}
                                disabled={!isNew} onClick={() => set('scope', sc.value)}
                                className={cn('flex cursor-pointer flex-col items-start rounded-md border px-3 py-2 text-left text-sm hover:bg-muted/50 disabled:cursor-not-allowed disabled:opacity-60',
                                  state.scope === sc.value && 'border-primary bg-muted ring-1 ring-primary')}>
                          <span className="flex items-center gap-1.5 font-medium"><FolderIcon size={14} /> {sc.label}</span>
                          <span className="font-mono text-[11px] text-muted-foreground break-all">{sc.path}</span>
                        </button>
                      ))}
                    </div>
                    <p className="text-xs text-muted-foreground">
                      The directory the spec file is saved in; it sets the agent's scope.{!isNew && ' Moving an existing agent isn\'t supported.'}
                    </p>
                  </div>

                  {state.scope === 'project' && (
                    <div className="grid gap-4 sm:grid-cols-2">
                      <Field label="Working directory" htmlFor="agent-cwd" hint="Optional. The session's directory is used otherwise.">
                        <Input id="agent-cwd" className="font-mono" value={state.workingDir} placeholder="/path/to/project"
                               onChange={(e) => set('workingDir', e.target.value)} />
                      </Field>
                      <Field label="Allowed directories" htmlFor="agent-dirs" hint="One per line. Optional.">
                        <Textarea id="agent-dirs" className="min-h-9 font-mono text-xs" value={state.allowedDirs}
                                  placeholder="/path/to/data" onChange={(e) => set('allowedDirs', e.target.value)} />
                      </Field>
                    </div>
                  )}
                </div>
              )}

              {tab === 'model' && (
                <div className="flex flex-col gap-5">
                  <Field label="Model" error={visibleErrors.model} hint="Pick a model, or type any provider:model id.">
                    <ModelCombobox value={state.model} onChange={(v) => set('model', v)} invalid={!!visibleErrors.model} />
                  </Field>

                  <div className="flex flex-col gap-2">
                    <Label>Parameters</Label>
                    {state.params.length === 0 && <p className="text-sm text-muted-foreground">None; the provider's defaults apply.</p>}
                    {state.params.map((p) => {
                      const known = KNOWN_PARAMS.find((k) => k.key === p.key.trim())
                      const update = (patch: Partial<ParamRow>) => set('params', state.params.map((r) => (r.id === p.id ? { ...r, ...patch } : r)))
                      return (
                        <div key={p.id} className="flex items-center gap-1.5">
                          <Input className="w-2/5 font-mono" value={p.key} placeholder="name" onChange={(e) => update({ key: e.target.value })} />
                          {known && !known.integer && known.max !== undefined ? (
                            <div className="flex flex-1 items-center gap-2">
                              <input type="range" className="flex-1 accent-primary" min={known.min} max={known.max} step={0.05}
                                     value={Number(p.value) || 0} onChange={(e) => update({ value: e.target.value })} />
                              <Input className="w-20 font-mono" value={p.value} onChange={(e) => update({ value: e.target.value })} />
                            </div>
                          ) : (
                            <Input className="flex-1 font-mono" value={p.value} placeholder={known?.hint || 'value (text, number or JSON)'}
                                   onChange={(e) => update({ value: e.target.value })} />
                          )}
                          <Button type="button" size="icon" variant="ghost" title="Remove parameter"
                                  onClick={() => set('params', state.params.filter((r) => r.id !== p.id))}>
                            <Trash2Icon />
                          </Button>
                        </div>
                      )
                    })}
                    {visibleErrors.params && <p className="text-xs text-destructive">{visibleErrors.params}</p>}
                    <div className="flex flex-wrap items-center gap-1.5">
                      {KNOWN_PARAMS.filter((k) => !usedParamKeys.has(k.key)).map((k) => (
                        <Button key={k.key} type="button" size="sm" variant="outline" title={k.hint}
                                onClick={() => set('params', [...state.params, { id: rowId(), key: k.key, value: k.defaultValue }])}>
                          <PlusIcon /> {k.key}
                        </Button>
                      ))}
                      <Button type="button" size="sm" variant="ghost"
                              onClick={() => set('params', [...state.params, { id: rowId(), key: '', value: '' }])}>
                        <PlusIcon /> Custom
                      </Button>
                    </div>
                  </div>
                </div>
              )}

              {tab === 'tools' && (
                <div className="flex flex-col gap-5">
                  <section className="flex flex-col gap-2">
                    <div className="flex items-baseline justify-between gap-2">
                      <Label>MCP servers</Label>
                      <span className="text-xs text-muted-foreground">{state.mcpServers.length} of {servers.length} assigned</span>
                    </div>
                    <p className="text-xs text-muted-foreground">The agent connects to these servers. Pick which of their tools it may call below.</p>
                    {catalogLoading && <Skeleton className="h-16 w-full" />}
                    {!catalogLoading && servers.length === 0 && <p className="text-sm text-muted-foreground">No MCP servers configured.</p>}
                    <div className="grid gap-2 sm:grid-cols-2">
                      {servers.map((server) => {
                        const on = state.mcpServers.includes(server.name)
                        const total = toolGroups.byServer[server.name]?.length || 0
                        const picked = state.tools.filter((t) => mcpServerOfTool(t) === server.name).length
                        return (
                          <Check key={server.name} checked={on} onChange={(v) => toggleServer(server.name, v)}>
                            <span className="flex items-center gap-1.5 font-medium">
                              <PlugIcon size={14} className="shrink-0" /> <span className="truncate">{server.name}</span>
                              {server.type && <Badge variant="outline" className="text-[10px]">{server.type}</Badge>}
                            </span>
                            <span className="block text-xs text-muted-foreground">
                              {on ? `${picked} of ${total} tools allowed` : `${total} tools`}
                            </span>
                          </Check>
                        )
                      })}
                      {unknownServers.map((name) => (
                        <Check key={name} checked onChange={() => toggleServer(name, false)} className="border-amber-500/50">
                          <span className="font-medium">{name}</span>
                          <Missing>Not configured in mcp.json</Missing>
                        </Check>
                      ))}
                    </div>
                  </section>

                  <section className="flex flex-col gap-3">
                    <div className="flex items-baseline justify-between gap-2">
                      <Label>Tools</Label>
                      <span className="text-xs text-muted-foreground">Only the selected tools can be called by the model.</span>
                    </div>
                    <SearchInput value={toolFilter} onChange={setToolFilter} placeholder="Filter tools …" />
                    {catalogLoading && <Skeleton className="h-24 w-full" />}

                    {[
                      { key: 'builtin', title: 'Built-in', icon: TerminalIcon, list: toolGroups.builtin, note: undefined as string | undefined },
                      ...state.mcpServers.filter((s) => knownServerNames.has(s)).map((s) => ({
                        key: s, title: `MCP · ${s}`, icon: PlugIcon, list: toolGroups.byServer[s] || [],
                        note: toolGroups.byServer[s] ? undefined : 'No tools were discovered for this server. It may have been unreachable when geenii started.',
                      })),
                    ].map((group) => {
                      if (catalogLoading) return null
                      const visible = group.list.filter(toolMatches)
                      const names = group.list.map((t) => t.name)
                      const picked = names.filter((n) => state.tools.includes(n)).length
                      if (toolFilter && visible.length === 0) return null
                      return (
                        <div key={group.key} className="flex flex-col gap-1.5">
                          <div className="flex items-center justify-between gap-2">
                            <h5 className="flex items-center gap-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                              <group.icon size={12} /> {group.title}
                              <span className="font-normal normal-case tracking-normal">({picked}/{names.length})</span>
                            </h5>
                            {names.length > 0 && (
                              <div className="flex gap-1">
                                <Button type="button" size="sm" variant="ghost" className="h-6 px-2 text-xs"
                                        disabled={picked === names.length} onClick={() => setGroupTools(names, true)}>All</Button>
                                <Button type="button" size="sm" variant="ghost" className="h-6 px-2 text-xs"
                                        disabled={picked === 0} onClick={() => setGroupTools(names, false)}>None</Button>
                              </div>
                            )}
                          </div>
                          {group.note && <Missing>{group.note}</Missing>}
                          <div className="grid gap-1.5 sm:grid-cols-2">
                            {visible.map((t) => (
                              <Check key={t.name} checked={state.tools.includes(t.name)} onChange={(v) => toggleTool(t.name, v)}
                                     title={t.description || t.name} className="py-1.5">
                                <span className="block truncate font-mono text-xs">{shortToolName(t.name)}</span>
                                {t.description && <span className="line-clamp-1 text-xs text-muted-foreground">{t.description.trim()}</span>}
                              </Check>
                            ))}
                          </div>
                        </div>
                      )
                    })}

                    {!catalogLoading && state.mcpServers.length === 0 && (
                      <p className="text-xs text-muted-foreground">Assign an MCP server above to choose from its tools.</p>
                    )}

                    {unknownTools.length > 0 && (
                      <div className="flex flex-col gap-1.5">
                        <Missing>Assigned but not available on the server ({unknownTools.length})</Missing>
                        <div className="flex flex-wrap gap-1">
                          {unknownTools.map((t) => (
                            <Badge key={t} variant="outline" className="gap-1 border-amber-500/50 font-mono">
                              {t}
                              <button type="button" className="cursor-pointer" title="Remove" onClick={() => toggleTool(t, false)}>
                                <XIcon className="size-3" />
                              </button>
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}
                  </section>
                </div>
              )}

              {tab === 'skills' && (
                <div className="flex flex-col gap-3">
                  <div className="flex items-baseline justify-between gap-2">
                    <Label>Skills</Label>
                    <span className="text-xs text-muted-foreground">{state.skills.length} of {skills.length} assigned</span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Skills are activated when relevant, or with <code className="font-mono">/&lt;skill&gt;</code> in the chat.
                  </p>
                  <SearchInput value={skillFilter} onChange={setSkillFilter} placeholder="Filter skills …" />
                  {catalogLoading && <Skeleton className="h-24 w-full" />}
                  {!catalogLoading && skills.length === 0 && <p className="text-sm text-muted-foreground">No skills found.</p>}
                  <div className="grid gap-2 sm:grid-cols-2">
                    {filteredSkills.map((s) => (
                      <Check key={s.name} checked={state.skills.includes(s.name)} title={s.description}
                             onChange={(v) => set('skills', v ? [...state.skills, s.name] : state.skills.filter((n) => n !== s.name))}>
                        <span className="block truncate font-mono text-xs font-medium">{s.name}</span>
                        <span className="line-clamp-2 text-xs text-muted-foreground">{s.description}</span>
                      </Check>
                    ))}
                    {unknownSkills.map((name) => (
                      <Check key={name} checked onChange={() => set('skills', state.skills.filter((n) => n !== name))}
                             className="border-amber-500/50">
                        <span className="block font-mono text-xs font-medium">{name}</span>
                        <Missing>Skill not found</Missing>
                      </Check>
                    ))}
                  </div>
                </div>
              )}

              {tab === 'instructions' && (
                <div className="flex flex-col gap-4">
                  <Field label="System prompt" htmlFor="agent-system"
                         hint="Optional. Short and frontmatter-friendly; it comes first, before the instructions.">
                    <Textarea id="agent-system" className="min-h-20 font-mono text-xs" value={state.system}
                              placeholder="You are a concise assistant …" onChange={(e) => set('system', e.target.value)} />
                  </Field>
                  <div className="flex flex-col gap-1.5">
                    <div className="flex items-center justify-between gap-2">
                      <Label htmlFor="agent-instructions">Instructions</Label>
                      <div className="inline-flex rounded-md border p-0.5">
                        <Button type="button" size="sm" className="h-6 px-2 text-xs" variant={instructionsPreview ? 'ghost' : 'secondary'}
                                onClick={() => setInstructionsPreview(false)}>Write</Button>
                        <Button type="button" size="sm" className="h-6 px-2 text-xs" variant={instructionsPreview ? 'secondary' : 'ghost'}
                                onClick={() => setInstructionsPreview(true)}>Preview</Button>
                      </div>
                    </div>
                    {instructionsPreview ? (
                      <div className={cn('min-h-80 overflow-auto rounded-md border p-3 text-sm', markdownClass)}>
                        {state.instructions.trim()
                          ? <OutputDataMarkdown data={state.instructions} />
                          : <span className="text-muted-foreground">Nothing to preview.</span>}
                      </div>
                    ) : (
                      <Textarea id="agent-instructions" className="min-h-80 font-mono text-xs" value={state.instructions}
                                spellCheck={false} placeholder={'# My Agent\n\nYou are …\n\n## Workflow\n\n1. …'}
                                onChange={(e) => set('instructions', e.target.value)} />
                    )}
                    <p className="text-xs text-muted-foreground">Markdown, saved as the body of the spec file. Added to the system prompt.</p>
                  </div>
                </div>
              )}

              {tab === 'preview' && (
                <div className="flex flex-col gap-2">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-xs text-muted-foreground break-all">
                      {SCOPES.find((s) => s.value === state.scope)?.path}/{state.name.trim() || '<name>'}.md
                    </span>
                    <Button type="button" size="sm" variant="ghost" onClick={copyMarkdown}>
                      {copied ? <CheckIcon /> : <CopyIcon />} {copied ? 'Copied' : 'Copy'}
                    </Button>
                  </div>
                  <pre className="max-h-[32rem] overflow-auto rounded-md border bg-muted p-3 font-mono text-xs whitespace-pre-wrap">{markdown}</pre>
                </div>
              )}
            </>
          )}
        </CardContent>

        <div className="flex flex-col gap-2 border-t px-6 py-4">
          {showErrors && Object.keys(errors).length > 0 && (
            <p className="text-sm text-destructive">Fix the highlighted fields first.</p>
          )}
          {submitError && <div className="rounded-md border border-destructive/50 p-3 text-sm text-destructive">{submitError}</div>}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={onCancel} disabled={submitting}>Cancel</Button>
            <Button type="submit" disabled={submitting || loadingAgent || !!loadError}>
              {submitting ? <LoaderIcon className="animate-spin" /> : <SaveIcon />}
              {isNew ? 'Create agent' : 'Save changes'}
            </Button>
          </div>
        </div>
      </form>
    </Card>
  )
}

export default AgentConfigEditor
