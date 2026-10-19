import React from 'react'
import {
  ArrowLeftIcon,
  BotIcon,
  BrainIcon,
  InfoIcon,
  FileTextIcon,
  PlugIcon,
  RefreshCwIcon,
  ScrollTextIcon,
  SlidersHorizontalIcon,
  SparklesIcon,
  TerminalIcon,
  WrenchIcon,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge.tsx'
import { Button } from '@/components/ui/button.tsx'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.tsx'
import { Skeleton } from '@/components/ui/skeleton.tsx'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog.tsx'
import { OutputDataMarkdown } from '@/components/output-data-markdown.tsx'
import { markdownClass } from '@/components/xchat/parts/media-parts.tsx'
import { useApi } from '@/context/api-context.tsx'
import { ToolType } from '@/app/tools/tool-types.ts'
import AgentChat from '@/app/agents/agent-chat.tsx'
import {
  AgentCommandType,
  AgentDetailType,
  mcpServerOfTool,
  shortToolName,
} from '@/app/agents/agent-types.ts'

const SectionTitle = ({ icon: Icon, children, count }: {
  icon: React.ElementType,
  children: React.ReactNode,
  count?: number
}) => (
  <CardTitle className="flex items-center gap-2 text-base">
    <Icon size={16} className="text-muted-foreground" />
    {children}
    {count !== undefined && <span className="text-sm font-normal text-muted-foreground">({count})</span>}
  </CardTitle>
)

const Empty = ({ children }: { children: React.ReactNode }) => (
  <p className="text-sm text-muted-foreground italic">{children}</p>
)

const ModelSection = ({ agent }: { agent: AgentDetailType }) => {
  const params = Object.entries(agent.model_parameters || {})
  return (
    <Card className="gap-4">
      <CardHeader><SectionTitle icon={BrainIcon}>Model</SectionTitle></CardHeader>
      <CardContent className="flex flex-col gap-3">
        <code className="w-fit rounded-md bg-muted px-2 py-1 text-sm">{agent.model || 'default'}</code>
        <div className="flex flex-col gap-1">
          <h4 className="flex items-center gap-1 text-xs font-medium text-muted-foreground">
            <SlidersHorizontalIcon size={12} /> Parameters
          </h4>
          {params.length === 0
            ? <Empty>Provider defaults</Empty>
            : (
              <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
                {params.map(([key, value]) => (
                  <React.Fragment key={key}>
                    <dt className="font-mono text-muted-foreground">{key}</dt>
                    <dd className="font-mono break-all">{typeof value === 'object' ? JSON.stringify(value) : String(value)}</dd>
                  </React.Fragment>
                ))}
              </dl>
            )}
        </div>
      </CardContent>
    </Card>
  )
}

const ToolRow = ({ name, description }: { name: string, description?: string | null }) => (
  <li className="flex flex-col gap-0.5">
    <span className="font-mono text-sm" title={name}>{shortToolName(name)}</span>
    {description && <span className="text-xs text-muted-foreground line-clamp-2">{description.trim()}</span>}
  </li>
)

const ToolsSection = ({ agent, toolDescriptions }: {
  agent: AgentDetailType,
  toolDescriptions: Record<string, string | null | undefined>
}) => {
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
    <Card className="gap-4">
      <CardHeader>
        <SectionTitle icon={WrenchIcon} count={tools.length}>Tools</SectionTitle>
        <CardDescription>Only the tools listed here can be called by the model.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {tools.length === 0 && groups.servers.length === 0 && <Empty>This agent cannot call any tools.</Empty>}

        {groups.builtin.length > 0 && (
          <div className="flex flex-col gap-2">
            <h4 className="flex items-center gap-1 text-xs font-medium text-muted-foreground uppercase tracking-wide">
              <TerminalIcon size={12} /> Built-in
            </h4>
            <ul className="flex flex-col gap-2">
              {groups.builtin.map((t) => <ToolRow key={t} name={t} description={toolDescriptions[t]} />)}
            </ul>
          </div>
        )}

        {groups.servers.map(([server, serverTools]) => (
          <div key={server} className="flex flex-col gap-2">
            <h4 className="flex items-center gap-1 text-xs font-medium text-muted-foreground uppercase tracking-wide">
              <PlugIcon size={12} /> MCP · {server}
            </h4>
            {serverTools.length === 0
              ? <Empty>Server is connected, but none of its tools are allowed.</Empty>
              : (
                <div className="flex flex-wrap gap-1">
                  {serverTools.map((t) => <Badge key={t} variant="outline" className="font-mono" title={t}>{shortToolName(t)}</Badge>)}
                </div>
              )}
          </div>
        ))}
      </CardContent>
    </Card>
  )
}

const SkillsSection = ({ agent, commands }: { agent: AgentDetailType, commands: AgentCommandType[] }) => {
  const skills = agent.skills || []
  const descriptions = React.useMemo(
    () => Object.fromEntries(commands.map((c) => [c.command.toLowerCase(), c.description])),
    [commands],
  )
  return (
    <Card className="gap-4">
      <CardHeader>
        <SectionTitle icon={SparklesIcon} count={skills.length}>Skills</SectionTitle>
        <CardDescription>Activated automatically when relevant, or with <code>/&lt;skill&gt;</code> in the chat.</CardDescription>
      </CardHeader>
      <CardContent>
        {skills.length === 0
          ? <Empty>No skills</Empty>
          : (
            <ul className="flex flex-col gap-2">
              {skills.map((s) => (
                <li key={s} className="flex flex-col gap-0.5">
                  <Badge className="w-fit">{s}</Badge>
                  {descriptions[s.toLowerCase()] && (
                    <span className="text-xs text-muted-foreground line-clamp-3">{descriptions[s.toLowerCase()]}</span>
                  )}
                </li>
              ))}
            </ul>
          )}
      </CardContent>
    </Card>
  )
}

/** Plain (not a card): shown full width below the other sections in the details dialog. */
const InstructionsSection = ({ agent }: { agent: AgentDetailType }) => {
  const system = agent.system?.trim()
  const instructions = agent.instructions?.trim()
  return (
    <section className="flex flex-col gap-3 border-t pt-4">
      <h3 className="flex items-center gap-2 font-semibold">
        <ScrollTextIcon size={16} className="text-muted-foreground" /> Instructions
      </h3>
      {!system && !instructions && <Empty>None; the default system prompt is used.</Empty>}
      {system && (
        <div className="flex flex-col gap-1">
          <h4 className="text-xs font-medium text-muted-foreground">System prompt</h4>
          <pre className="overflow-x-auto rounded-md bg-muted p-3 text-xs whitespace-pre-wrap">{system}</pre>
        </div>
      )}
      {instructions && (
        <div className={`text-sm ${markdownClass}`}>
          <OutputDataMarkdown data={instructions} />
        </div>
      )}
    </section>
  )
}

const CountBadge = ({ icon: Icon, count, label, names }: {
  icon: React.ElementType, count: number, label: string, names: string[]
}) => (
  <Badge variant="outline" className={count === 0 ? 'text-muted-foreground' : ''}
         title={count ? `${label}:\n${names.join('\n')}` : `No ${label.toLowerCase()}`}>
    <Icon /> {count}
  </Badge>
)

/** Short agent info for the chat card header; everything else is in the details dialog. */
const AgentShortInfo = ({ agent, onShowDetails }: { agent: AgentDetailType, onShowDetails: () => void }) => {
  const tools = agent.tools || []
  const mcpServers = agent.mcp_servers || []
  const skills = agent.skills || []
  const description = agent.description?.trim()

  return (
    <div className="flex min-w-0 items-center gap-2">
      <Button size="icon" variant="ghost" className="size-8 shrink-0" asChild title="All agents">
        <a href="#/agents"><ArrowLeftIcon /></a>
      </Button>
      <div className="min-w-0 flex-1">
        <div className="flex min-w-0 items-center gap-2">
          <h2 className="truncate font-semibold">{agent.label || agent.name}</h2>
          <Badge variant="secondary" className="hidden max-w-48 truncate font-mono sm:inline-flex" title={`Model: ${agent.model || 'default'}`}>
            <BrainIcon /> {agent.model || 'default'}
          </Badge>
        </div>
        {description && <p className="truncate text-xs text-muted-foreground" title={description}>{description}</p>}
      </div>
      <div className="hidden shrink-0 items-center gap-1 md:flex">
        <CountBadge icon={WrenchIcon} count={tools.length} label="Tools" names={tools.map(shortToolName)} />
        <CountBadge icon={PlugIcon} count={mcpServers.length} label="MCP servers" names={mcpServers} />
        <CountBadge icon={SparklesIcon} count={skills.length} label="Skills" names={skills} />
      </div>
      <Button size="sm" variant="ghost" className="shrink-0" onClick={onShowDetails} title="Agent details">
        <InfoIcon /> <span className="hidden sm:inline">Details</span>
      </Button>
    </div>
  )
}

/** All of the agent's capabilities: model parameters, tools, skills and instructions. */
const AgentDetailsDialog = ({ agent, commands, toolDescriptions, open, onOpenChange, loading, onRefresh }: {
  agent: AgentDetailType
  commands: AgentCommandType[]
  toolDescriptions: Record<string, string | null | undefined>
  open: boolean
  onOpenChange: (open: boolean) => void
  loading: boolean
  onRefresh: () => void
}) => (
  <Dialog open={open} onOpenChange={onOpenChange}>
    <DialogContent className="flex max-h-[85svh] flex-col gap-4 sm:max-w-5xl">
      <DialogHeader className="pr-8">
        <div className="flex flex-wrap items-center gap-2">
          <BotIcon size={20} className="text-muted-foreground" />
          <DialogTitle>{agent.label || agent.name}</DialogTitle>
          {agent.label && <span className="font-mono text-sm text-muted-foreground">{agent.name}</span>}
          {agent.class_name && (
            <Badge variant="secondary" title={agent.class_name}>{agent.class_name.split('.').pop()}</Badge>
          )}
          <Button size="icon" variant="ghost" className="ml-auto size-8" onClick={onRefresh} disabled={loading} title="Refresh">
            <RefreshCwIcon className={loading ? 'animate-spin' : ''} />
          </Button>
        </div>
        <DialogDescription className="text-left whitespace-pre-line">
          {agent.description?.trim() || 'No description'}
        </DialogDescription>
      </DialogHeader>

      <div className="-mx-6 flex min-h-0 flex-col gap-4 overflow-y-auto px-6 pb-1">
        <div className="grid gap-4 lg:grid-cols-3">
          <ModelSection agent={agent} />
          <SkillsSection agent={agent} commands={commands} />
          <ToolsSection agent={agent} toolDescriptions={toolDescriptions} />
        </div>
        <InstructionsSection agent={agent} />
      </div>

      {agent.file_path && (
        <p className="flex items-center gap-1 text-xs text-muted-foreground">
          <FileTextIcon size={12} className="shrink-0" />
          <span className="truncate font-mono" title={agent.file_path}>{agent.file_path}</span>
        </p>
      )}
    </DialogContent>
  </Dialog>
)

/**
 * One agent: a chat with it, whose header shows the agent's short info.
 * The full capabilities (model parameters, tools, skills, instructions) open in a dialog.
 */
const AgentView = ({ name, contextId }: { name: string, contextId: string }) => {
  const { fetchJson } = useApi()

  const [agent, setAgent] = React.useState<AgentDetailType | null>(null)
  const [commands, setCommands] = React.useState<AgentCommandType[]>([])
  const [toolDescriptions, setToolDescriptions] = React.useState<Record<string, string | null | undefined>>({})
  const [loading, setLoading] = React.useState<boolean>(true)
  const [error, setError] = React.useState<string | null>(null)
  const [detailsOpen, setDetailsOpen] = React.useState<boolean>(false)

  const load = React.useCallback(async () => {
    setLoading(true)
    setError(null)
    const path = `/api/v1/agents/${encodeURIComponent(name)}`
    // commands (skill descriptions) and tool definitions only add detail, so their failure is not fatal
    const [agentResult, commandsResult, toolsResult] = await Promise.allSettled([
      fetchJson(path) as Promise<AgentDetailType>,
      fetchJson(`${path}/commands`) as Promise<AgentCommandType[]>,
      fetchJson('/api/v1/tools/') as Promise<ToolType[]>,
    ])
    if (agentResult.status === 'fulfilled') {
      setAgent(agentResult.value)
    } else {
      console.error('Error fetching agent', agentResult.reason)
      setAgent(null)
      setError(agentResult.reason?.message || 'Unknown error')
    }
    setCommands(commandsResult.status === 'fulfilled' ? commandsResult.value : [])
    setToolDescriptions(toolsResult.status === 'fulfilled'
      ? Object.fromEntries(toolsResult.value.map((t) => [t.name, t.description]))
      : {})
    setLoading(false)
  }, [fetchJson, name, setLoading, setError, setAgent, setCommands, setToolDescriptions])

  React.useEffect(() => {
    load()
  }, [load])

  return (
    // fills the viewport below the nav (MainContent padding included), so the chat gets the remaining height
    <div className="flex h-[calc(100svh-6rem)] min-h-[32rem] flex-col gap-4 md:h-[calc(100svh-7rem)]">
      {error && (
        <div className="flex shrink-0 items-center justify-between gap-2 rounded-lg border border-destructive/50 p-4 text-sm text-destructive">
          <span>Failed to load agent "{name}": {error}</span>
          <Button size="sm" variant="ghost" asChild><a href="#/agents"><ArrowLeftIcon /> Agents</a></Button>
        </div>
      )}

      {loading && !agent && <Skeleton className="flex-1 rounded-xl" />}

      {agent && (
        <>
          <AgentChat
            key={agent.name}
            contextId={contextId}
            agent={agent}
            className="min-h-80 flex-1"
            header={<AgentShortInfo agent={agent} onShowDetails={() => setDetailsOpen(true)} />}
          />
          <AgentDetailsDialog agent={agent} commands={commands} toolDescriptions={toolDescriptions}
                              open={detailsOpen} onOpenChange={setDetailsOpen} loading={loading} onRefresh={load} />
        </>
      )}
    </div>
  )
}

export default AgentView
