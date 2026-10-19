import * as React from 'react'
import {
  BotIcon, BracesIcon, BrainIcon, ChevronRightIcon, ExternalLinkIcon, ListIcon, PlugIcon, RefreshCwIcon,
  ScrollTextIcon, SearchIcon, SparklesIcon, TerminalIcon, WrenchIcon, XIcon,
} from 'lucide-react'
import {
  AgentCommandType, AgentDetailType, AgentType, agentUrl, mcpServerOfTool, shortToolName,
} from '@/app/agents/agent-types.ts'
import JsonView from '@/components/json-view.tsx'
import { OutputDataMarkdown } from '@/components/output-data-markdown.tsx'
import { markdownClass } from '@/components/xchat/parts/media-parts.tsx'
import { Badge } from '@/components/ui/badge.tsx'
import { Button } from '@/components/ui/button.tsx'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.tsx'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible.tsx'
import { Input } from '@/components/ui/input.tsx'
import { Skeleton } from '@/components/ui/skeleton.tsx'
import { useApi } from '@/context/api-context.tsx'
import { cn } from 'cn'

export const Empty = ({ children }: { children: React.ReactNode }) => (
  <span className="text-sm text-muted-foreground">{children}</span>
)

/** A collapsible section of the details card */
export const Section = ({ icon: Icon, title, count, defaultOpen = true, children }: {
  icon: React.ElementType
  title: string
  count?: number
  defaultOpen?: boolean
  children: React.ReactNode
}) => {
  const [open, setOpen] = React.useState(defaultOpen)
  return (
    <Collapsible open={open} onOpenChange={setOpen} className="flex flex-col gap-2">
      <CollapsibleTrigger className="flex cursor-pointer items-center gap-1.5 text-sm font-semibold">
        <ChevronRightIcon size={16} className={cn('transition-transform', open && 'rotate-90')} />
        <Icon size={14} className="text-muted-foreground" /> {title}
        {count !== undefined && <span className="font-normal text-muted-foreground">({count})</span>}
      </CollapsibleTrigger>
      <CollapsibleContent className="pl-5.5">{children}</CollapsibleContent>
    </Collapsible>
  )
}

const ModelSection = ({ agent }: { agent: AgentType }) => {
  const params = Object.entries(agent.model_parameters || {})
  return (
    <Section icon={BrainIcon} title="Model">
      <dl className="grid grid-cols-[max-content_minmax(0,1fr)] gap-x-4 gap-y-1 text-sm">
        <dt className="text-muted-foreground">Model</dt>
        <dd className="font-mono break-all">{agent.model || <Empty>default</Empty>}</dd>
        {params.map(([key, value]) => (
          <React.Fragment key={key}>
            <dt className="font-mono text-muted-foreground">{key}</dt>
            <dd className="font-mono break-all">{typeof value === 'object' ? JSON.stringify(value) : String(value)}</dd>
          </React.Fragment>
        ))}
      </dl>
      {params.length === 0 && <p className="mt-1 text-xs text-muted-foreground">No model parameters; provider defaults apply.</p>}
    </Section>
  )
}

const ToolsSection = ({ agent }: { agent: AgentType }) => {
  const tools = agent.tools || []
  // built-in tools first, then one group per MCP server (including servers without allowed tools)
  const groups = React.useMemo(() => {
    const builtin: string[] = []
    const byServer: Record<string, string[]> = {}
    ;(agent.mcp_servers || []).forEach((s) => { byServer[s] = [] })
    tools.forEach((t) => {
      const server = mcpServerOfTool(t)
      if (server) (byServer[server] ||= []).push(t)
      else builtin.push(t)
    })
    return { builtin, servers: Object.entries(byServer).sort(([a], [b]) => a.localeCompare(b)) }
  }, [tools, agent.mcp_servers])

  return (
    <Section icon={WrenchIcon} title="Tools" count={tools.length}>
      <div className="flex flex-col gap-3">
        {tools.length === 0 && groups.servers.length === 0 && <Empty>This agent cannot call any tools.</Empty>}
        {groups.builtin.length > 0 && (
          <div className="flex flex-col gap-1">
            <h5 className="flex items-center gap-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              <TerminalIcon size={12} /> Built-in
            </h5>
            <div className="flex flex-wrap gap-1">
              {groups.builtin.map((t) => <Badge key={t} variant="outline" className="font-mono">{t}</Badge>)}
            </div>
          </div>
        )}
        {groups.servers.map(([server, serverTools]) => (
          <div key={server} className="flex flex-col gap-1">
            <h5 className="flex items-center gap-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              <PlugIcon size={12} /> MCP · {server}
            </h5>
            {serverTools.length === 0
              ? <Empty>Server is connected, but none of its tools are allowed.</Empty>
              : (
                <div className="flex flex-wrap gap-1">
                  {serverTools.map((t) => <Badge key={t} variant="outline" className="font-mono" title={t}>{shortToolName(t)}</Badge>)}
                </div>
              )}
          </div>
        ))}
      </div>
    </Section>
  )
}

const SkillsSection = ({ agent, commands }: { agent: AgentType, commands: AgentCommandType[] }) => {
  const skills = agent.skills || []
  const descriptions = React.useMemo(
    () => Object.fromEntries(commands.map((c) => [c.command.toLowerCase(), c.description])),
    [commands],
  )
  return (
    <Section icon={SparklesIcon} title="Skills" count={skills.length}>
      {skills.length === 0
        ? <Empty>No skills</Empty>
        : (
          <ul className="flex flex-col gap-2">
            {skills.map((s) => (
              <li key={s} className="flex flex-col gap-0.5">
                <Badge className="w-fit">{s}</Badge>
                {descriptions[s.toLowerCase()] && (
                  <span className="text-xs text-muted-foreground line-clamp-2">{descriptions[s.toLowerCase()]}</span>
                )}
              </li>
            ))}
          </ul>
        )}
    </Section>
  )
}

const InstructionsSection = ({ agent, loading }: { agent: AgentDetailType | null, loading: boolean }) => {
  const system = agent?.system?.trim()
  const instructions = agent?.instructions?.trim()
  return (
    <Section icon={ScrollTextIcon} title="Instructions" defaultOpen={false}>
      {loading && !agent && <Skeleton className="h-24 w-full" />}
      {agent && !system && !instructions && <Empty>None; the default system prompt is used.</Empty>}
      {system && (
        <div className="flex flex-col gap-1">
          <h5 className="text-xs font-medium text-muted-foreground">System prompt</h5>
          <pre className="max-h-64 overflow-auto rounded-md bg-muted p-3 text-xs whitespace-pre-wrap">{system}</pre>
        </div>
      )}
      {instructions && (
        <div className={cn('max-h-96 overflow-auto rounded-md border p-3 text-sm', markdownClass)}>
          <OutputDataMarkdown data={instructions} />
        </div>
      )}
    </Section>
  )
}

const DESCRIPTION_MAX_CHARS = 280

/** Description capped at a few lines, with a toggle when it's longer */
export const AgentDescription = ({ description }: { description?: string | null }) => {
  const [expanded, setExpanded] = React.useState(false)
  const text = description?.trim()
  if (!text) return <CardDescription className="italic">No description</CardDescription>
  const long = text.length > DESCRIPTION_MAX_CHARS || text.split('\n').length > 3
  return (
    <CardDescription className="flex flex-col items-start gap-1">
      <span className={cn('whitespace-pre-line', long && !expanded && 'line-clamp-3')}>{text}</span>
      {long && (
        <button type="button" className="cursor-pointer text-xs font-medium text-foreground hover:underline"
                onClick={() => setExpanded(!expanded)} aria-expanded={expanded}>
          {expanded ? 'Show less' : 'Show more'}
        </button>
      )}
    </CardDescription>
  )
}

/** Details of one agent; the spec from the list is shown at once, instructions and skill descriptions are fetched */
const AgentConfigDetails = ({ agent, onClose }: { agent: AgentType, onClose: () => void }) => {
  const { fetchJson } = useApi()
  const [detail, setDetail] = React.useState<AgentDetailType | null>(null)
  const [commands, setCommands] = React.useState<AgentCommandType[]>([])
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)
  const [showRaw, setShowRaw] = React.useState(false)

  React.useEffect(() => {
    let cancelled = false
    const path = `/api/v1/agents/${encodeURIComponent(agent.name)}`
    Promise.allSettled([
      fetchJson(path) as Promise<AgentDetailType>,
      fetchJson(`${path}/commands`) as Promise<AgentCommandType[]>,
    ]).then(([detailResult, commandsResult]) => {
      if (cancelled) return
      if (detailResult.status === 'fulfilled') setDetail(detailResult.value)
      else setError(detailResult.reason?.message || 'Unknown error')
      // skill descriptions only add detail, so a failure here is not shown
      setCommands(commandsResult.status === 'fulfilled' ? commandsResult.value : [])
      setLoading(false)
    })
    return () => { cancelled = true }
  }, [fetchJson, agent.name])

  return (
    <Card className="gap-4">
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <CardTitle className="flex items-center gap-2">
              <BotIcon size={16} className="shrink-0" /> <span className="truncate">{agent.label || agent.name}</span>
              {agent.class_name && (
                <Badge variant="secondary" title={agent.class_name}>{agent.class_name.split('.').pop()}</Badge>
              )}
            </CardTitle>
            {agent.label && <p className="mt-1 font-mono text-xs text-muted-foreground">{agent.name}</p>}
          </div>
          <div className="flex shrink-0 items-center gap-1">
            <Button size="sm" variant="ghost" onClick={() => setShowRaw(!showRaw)} aria-pressed={showRaw}
                    title={showRaw ? 'Show details' : 'Show raw JSON'}>
              {showRaw ? <ListIcon /> : <BracesIcon />} {showRaw ? 'Details' : 'Raw JSON'}
            </Button>
            <Button size="sm" variant="ghost" asChild title="Open the agent">
              <a href={agentUrl(agent.name)}><ExternalLinkIcon /> Open</a>
            </Button>
            <Button size="icon" variant="ghost" onClick={onClose} title="Close">
              <XIcon />
            </Button>
          </div>
        </div>
        <AgentDescription description={agent.description} />
        {agent.file_path && (
          <p className="truncate font-mono text-xs text-muted-foreground" title={agent.file_path}>{agent.file_path}</p>
        )}
      </CardHeader>
      <CardContent className="flex flex-col gap-5">
        {error && (
          <div className="rounded-lg border border-destructive/50 p-3 text-sm text-destructive">
            Failed to load agent details: {error}
          </div>
        )}
        {showRaw ? (
          <JsonView src={detail || agent} className="max-w-full" />
        ) : (
          <>
            <ModelSection agent={agent} />
            <ToolsSection agent={agent} />
            <SkillsSection agent={agent} commands={commands} />
            <InstructionsSection agent={detail} loading={loading} />
          </>
        )}
      </CardContent>
    </Card>
  )
}

export const CountChip = ({ icon: Icon, count, label }: { icon: React.ElementType, count: number, label: string }) => (
  <span className={cn('flex items-center gap-0.5', count === 0 && 'opacity-50')} title={`${count} ${label}`}>
    <Icon size={12} /> {count}
  </span>
)

const LIST_DESCRIPTION_MAX_CHARS = 140

/** First paragraph of a description, cut at a word boundary */
export const capText = (text?: string | null, max = LIST_DESCRIPTION_MAX_CHARS) => {
  const first = (text || '').trim().split(/\n\s*\n/)[0].replace(/\s+/g, ' ')
  if (first.length <= max) return first
  const cut = first.slice(0, max)
  return `${cut.slice(0, cut.lastIndexOf(' ') > max * 0.6 ? cut.lastIndexOf(' ') : max).replace(/[\s.,;:]+$/, '')}…`
}

const AgentsAdminView = () => {
  const { fetchJson } = useApi()
  const [agents, setAgents] = React.useState<AgentType[]>([])
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)
  const [filter, setFilter] = React.useState('')
  const [selectedName, setSelectedName] = React.useState<string | null>(null)

  const fetchAgents = React.useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data: AgentType[] = await fetchJson('/api/v1/agents/')
      setAgents([...data].sort((a, b) => a.name.localeCompare(b.name)))
    } catch (err) {
      console.error('Error fetching agents', err)
      setError(err?.message || 'Unknown error')
    } finally {
      setLoading(false)
    }
  }, [fetchJson])

  React.useEffect(() => {
    fetchAgents()
  }, [fetchAgents])

  const filtered = React.useMemo(() => {
    const q = filter.trim().toLowerCase()
    return agents.filter((a) => !q || [a.name, a.label, a.description, a.model]
      .some((v) => v?.toLowerCase().includes(q)))
  }, [agents, filter])

  const selected = agents.find((a) => a.name === selectedName) || null

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-2">
        <div className="relative w-full max-w-xs">
          <SearchIcon size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input className="pl-8" placeholder="Filter agents ..." value={filter} onChange={(e) => setFilter(e.target.value)} />
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground whitespace-nowrap">
            {!loading && !error && `${agents.length} agent${agents.length === 1 ? '' : 's'}`}
          </span>
          <Button size="sm" variant="ghost" onClick={fetchAgents} disabled={loading}>
            <RefreshCwIcon className={loading ? 'animate-spin' : ''} /> Refresh
          </Button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/50 p-4 text-sm text-destructive">
          Failed to load agents: {error}
        </div>
      )}

      <div className={cn('grid gap-6', selected && 'lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]')}>
        <div className="flex min-w-0 flex-col gap-2">
          {loading && agents.length === 0 && [0, 1, 2].map((i) => <Skeleton key={i} className="h-16 w-full rounded-md" />)}
          {!loading && !error && filtered.length === 0 && (
            <p className="text-sm text-muted-foreground">{filter ? 'No agents match the filter.' : 'No agents configured.'}</p>
          )}
          {filtered.map((agent) => (
            <button key={agent.name} type="button"
                    className={cn('flex w-full cursor-pointer items-start gap-3 rounded-md border px-3 py-2 text-left hover:bg-muted/50',
                      agent.name === selectedName && 'border-primary bg-muted')}
                    onClick={() => setSelectedName(agent.name === selectedName ? null : agent.name)}>
              <BotIcon size={16} className="mt-0.5 shrink-0" />
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2 text-sm font-medium">
                  <span className="truncate">{agent.label || agent.name}</span>
                  <span className="flex shrink-0 items-center gap-2 text-xs font-normal text-muted-foreground">
                    <CountChip icon={WrenchIcon} count={agent.tools?.length || 0} label="tools" />
                    <CountChip icon={PlugIcon} count={agent.mcp_servers?.length || 0} label="MCP servers" />
                    <CountChip icon={SparklesIcon} count={agent.skills?.length || 0} label="skills" />
                  </span>
                </div>
                <p className="line-clamp-2 text-xs text-muted-foreground" title={agent.description?.trim()}>
                  {capText(agent.description) || <span className="italic">No description</span>}
                </p>
                {agent.model && (
                  <p className="flex items-center gap-1 truncate font-mono text-xs text-muted-foreground">
                    <BrainIcon size={12} className="shrink-0" /> {agent.model}
                  </p>
                )}
              </div>
            </button>
          ))}
        </div>

        {selected && (
          <div className="lg:sticky lg:top-20 lg:self-start">
            {/* keyed by name, so details are fetched once per selected agent */}
            <AgentConfigDetails key={selected.name} agent={selected} onClose={() => setSelectedName(null)} />
          </div>
        )}
      </div>
    </div>
  )
}

export const AgentsSettingsView = () => <AgentsAdminView />
