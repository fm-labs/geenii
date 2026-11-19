import { BrainIcon, FolderIcon, PlugIcon, SettingsIcon, SparklesIcon, StarIcon, WrenchIcon } from 'lucide-react'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card.tsx'
import { cn } from 'cn'
import { Badge } from '@/components/ui/badge.tsx'
import { Skeleton } from '@/components/ui/skeleton.tsx'
import { agentConfigUrl, agentUrl, AgentType, shortToolName } from '@/app/agents/agent-types.ts'
import {
  AgentIcon, AgentsEmpty, AgentsError, agentTitle, LauncherAgentsTabProps, visibleAgents,
} from '@/app/launcher/launcher-agents-shared.tsx'

const MAX_CARD_TOOLS = 5

/** Project agents: a full card with all info inline instead of an icon tile + popover */
const ProjectAgentCard = ({ agent, isStarred, onToggleStar }: {
  agent: AgentType
  isStarred: boolean
  onToggleStar: () => void
}) => {
  const tools = agent.tools || []
  const skills = agent.skills || []
  const mcpServers = agent.mcp_servers || []
  const hiddenTools = tools.slice(MAX_CARD_TOOLS)

  return (
    <Card
      className="relative h-full gap-4 transition hover:border-foreground/20 hover:shadow-md has-[a:focus-visible]:ring-2 has-[a:focus-visible]:ring-ring">
      {/* stretched link: the whole card launches the agent, the bookmark button sits above it */}
      <a href={agentUrl(agent.name)} className="absolute inset-0 z-0 rounded-xl outline-none"
         aria-label={`Launch ${agentTitle(agent)}`} />
      <CardHeader>
        <div className="flex items-start gap-3">
          <AgentIcon agent={agent} size="sm" />
          <div className="min-w-0 flex-1">
            <div className="flex items-start justify-between gap-2">
              <CardTitle className="truncate leading-tight">{agentTitle(agent)}</CardTitle>
              <div className="relative z-10 -mt-1 -mr-1 flex shrink-0 items-center">
                <a
                  href={agentConfigUrl(agent.name)}
                  className="rounded-full p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                  title="Configure"
                  aria-label={`Configure ${agentTitle(agent)}`}
                >
                  <SettingsIcon size={16} />
                </a>
                <button
                  type="button"
                  onClick={onToggleStar}
                  className="rounded-full p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                  title={isStarred ? 'Remove bookmark':'Bookmark'}
                >
                  <StarIcon size={16} className={cn(isStarred && 'fill-amber-400 text-amber-400')} />
                </button>
              </div>
            </div>
            {agent.label && <p className="truncate font-mono text-xs text-muted-foreground">{agent.name}</p>}
            {agent.model && (
              <p className="mt-1 flex items-center gap-1 text-xs text-muted-foreground" title="Model">
                <BrainIcon size={12} /> <span className="truncate font-mono">{agent.model}</span>
              </p>
            )}
          </div>
        </div>
        <CardDescription className="line-clamp-3" title={agent.description?.trim()}>
          {agent.description?.trim() || <span className="italic">No description</span>}
        </CardDescription>
      </CardHeader>

      <CardContent className="flex flex-col gap-2 text-sm">
        {mcpServers.length > 0 && (
          <div className="flex flex-wrap items-center gap-1">
            <PlugIcon size={14} className="mr-1 text-muted-foreground" aria-label="MCP servers" />
            {mcpServers.map((s) => <Badge key={s} variant="secondary">{s}</Badge>)}
          </div>
        )}
        <div className="flex flex-wrap items-center gap-1">
          <WrenchIcon size={14} className="mr-1 text-muted-foreground" aria-label="Tools" />
          {tools.length===0 && <span className="text-xs text-muted-foreground">No tools</span>}
          {tools.slice(0, MAX_CARD_TOOLS).map((t) => <Badge key={t} variant="outline"
                                                            title={t}>{shortToolName(t)}</Badge>)}
          {hiddenTools.length > 0 && (
            <Badge variant="outline" title={hiddenTools.join('\n')}>+{hiddenTools.length} more</Badge>
          )}
        </div>
        {skills.length > 0 && (
          <div className="flex flex-wrap items-center gap-1">
            <SparklesIcon size={14} className="mr-1 text-muted-foreground" aria-label="Skills" />
            {skills.map((s) => <Badge key={s}>{s}</Badge>)}
          </div>
        )}
      </CardContent>

      <CardFooter className="mt-auto border-t pt-4! text-xs text-muted-foreground">
        <FolderIcon size={12} className="mr-1 shrink-0" aria-label="Working directory" />
        {agent.working_dir
          ? <span className="truncate font-mono"
                  title={`Working directory: ${agent.working_dir}`}>{agent.working_dir}</span>
          :<span className="italic">No directory access</span>}
      </CardFooter>
    </Card>
  )
}

const CardSkeleton = () => (
  <Card className="gap-4 px-6">
    <div className="flex items-center gap-3">
      <Skeleton className="size-11 rounded-[13px]" />
      <div className="flex flex-col gap-2">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-3 w-24" />
      </div>
    </div>
    <Skeleton className="h-12 w-full" />
    <Skeleton className="h-5 w-2/3" />
  </Card>
)

/** The launcher's project tab: project-scoped agents as cards, filtered by the launcher search */
const LauncherProject = ({ agents, loading, error, query, starred, toggleStar }: LauncherAgentsTabProps) => {
  const visible = visibleAgents(agents, query, starred)

  return <>
    {error && <AgentsError error={error} />}

    {loading && (
      <section className="grid w-full grid-cols-1 gap-4 md:grid-cols-2">
        {[0, 1].map((i) => <CardSkeleton key={i} />)}
      </section>
    )}

    {!loading && visible.length > 0 && (
      <section role="tabpanel" className="grid w-full grid-cols-1 gap-4 md:grid-cols-2">
        {visible.map((agent) => (
          <ProjectAgentCard
            key={agent.name}
            agent={agent}
            isStarred={starred.includes(agent.name)}
            onToggleStar={() => toggleStar(agent.name)}
          />
        ))}
      </section>
    )}

    {!loading && !error && visible.length===0 && (
      <AgentsEmpty query={query} emptyText="No project agents found." />
    )}
  </>
}

export default LauncherProject
