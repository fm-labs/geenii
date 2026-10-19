import React from 'react'
import { BotIcon, BrainIcon, FolderIcon, PlugIcon, RefreshCwIcon, SparklesIcon, WrenchIcon } from 'lucide-react'
import { Badge } from '@/components/ui/badge.tsx'
import { Button } from '@/components/ui/button.tsx'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card.tsx'
import { Skeleton } from '@/components/ui/skeleton.tsx'
import { useApi } from '@/context/api-context.tsx'
import { agentUrl, AgentType, shortToolName } from '@/app/agents/agent-types.ts'
import { cn } from 'cn'

const MAX_VISIBLE_TOOLS = 5

/** GET /api/v1/projects/ */
type ProjectType = { path: string, trusted: boolean, exists: boolean }

type ScopeFilter = 'all' | 'global' | 'user' | 'project'
const SCOPE_TABS: { id: ScopeFilter, label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'global', label: 'Global' },
  { id: 'user', label: 'User' },
  { id: 'project', label: 'Project' },
]

const selectClass = 'h-8 max-w-72 truncate rounded-md border border-input bg-transparent px-2 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 dark:bg-input/30'

/** The project containing the agent's working dir (the innermost one for nested projects), or null. */
const projectOfAgent = (agent: AgentType, projects: ProjectType[]) => {
  const wd = agent.working_dir?.replace(/\/+$/, '')
  if (!wd) return null
  const matches = projects.filter((p) => wd === p.path || wd.startsWith(p.path.replace(/\/+$/, '') + '/'))
  return matches.sort((a, b) => b.path.length - a.path.length)[0]?.path ?? null
}

const AgentCard = ({ agent }: { agent: AgentType }) => {
  const tools = agent.tools || []
  const skills = agent.skills || []
  const mcpServers = agent.mcp_servers || []
  const visibleTools = tools.slice(0, MAX_VISIBLE_TOOLS)
  const hiddenTools = tools.slice(MAX_VISIBLE_TOOLS)

  return (
    <a href={agentUrl(agent.name)} className="block rounded-xl focus-visible:outline-2 focus-visible:outline-ring">
    <Card className="h-full gap-4 transition hover:shadow-md hover:border-foreground/20">
      <CardHeader>
        <div className="flex items-start gap-3">
          <div className="rounded-lg bg-muted p-2 text-muted-foreground">
            <BotIcon size={24} />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center justify-between gap-2">
              <CardTitle className="truncate">{agent.label || agent.name}</CardTitle>
              <div className="flex shrink-0 items-center gap-1">
                {agent.scope && (
                  <Badge variant="outline" className="capitalize"
                         title={agent.scope === 'project' && agent.working_dir
                           ? `Scope: project (${agent.working_dir})`
                           : `Scope: ${agent.scope}`}>
                    {agent.scope}
                  </Badge>
                )}
                {agent.class_name && (
                  <Badge variant="secondary" title={agent.class_name}>{agent.class_name.split('.').pop()}</Badge>
                )}
              </div>
            </div>
            {agent.label && <p className="text-xs text-muted-foreground mt-1">{agent.name}</p>}
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

      <CardContent className="flex flex-col gap-3 text-sm">
        {mcpServers.length > 0 && (
          <div className="flex flex-wrap items-center gap-1">
            <PlugIcon size={14} className="text-muted-foreground mr-1" aria-label="MCP servers" />
            {mcpServers.map((s) => <Badge key={s} variant="secondary">{s}</Badge>)}
          </div>
        )}
        <div className="flex flex-wrap items-center gap-1">
          <WrenchIcon size={14} className="text-muted-foreground mr-1" aria-label="Tools" />
          {tools.length === 0 && <span className="text-xs text-muted-foreground">No tools</span>}
          {visibleTools.map((t) => <Badge key={t} variant="outline" title={t}>{shortToolName(t)}</Badge>)}
          {hiddenTools.length > 0 && (
            <Badge variant="outline" title={hiddenTools.join('\n')}>+{hiddenTools.length} more</Badge>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-1">
          <SparklesIcon size={14} className="text-muted-foreground mr-1" aria-label="Skills" />
          {skills.length === 0 && <span className="text-xs text-muted-foreground">No skills</span>}
          {skills.map((s) => <Badge key={s}>{s}</Badge>)}
        </div>
      </CardContent>

      <CardFooter className="mt-auto border-t pt-4! text-xs text-muted-foreground">
        <FolderIcon size={12} className="mr-1 shrink-0" aria-label="Working directory" />
        {agent.working_dir
          ? <span className="truncate font-mono" title={`Working directory: ${agent.working_dir}`}>{agent.working_dir}</span>
          : <span className="italic" title="No working directory configured">No directory access</span>}
      </CardFooter>
    </Card>
    </a>
  )
}

const AgentCardSkeleton = () => (
  <Card className="gap-4 px-6">
    <div className="flex items-center gap-3">
      <Skeleton className="size-10 rounded-lg" />
      <div className="flex flex-col gap-2">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-3 w-24" />
      </div>
    </div>
    <Skeleton className="h-12 w-full" />
    <Skeleton className="h-5 w-2/3" />
  </Card>
)

const AgentsView = () => {
  const { fetchJson } = useApi()

  const [agents, setAgents] = React.useState<AgentType[]>([])
  const [loading, setLoading] = React.useState<boolean>(true)
  const [error, setError] = React.useState<string | null>(null)
  const [projects, setProjects] = React.useState<ProjectType[]>([])
  const [scope, setScope] = React.useState<ScopeFilter>('all')
  const [project, setProject] = React.useState<string>('')

  const fetchAgents = React.useCallback(async () => {
    setLoading(true)
    setError(null)
    // the projects only feed the filter, so their failure is not fatal
    const [agentsResult, projectsResult] = await Promise.allSettled([
      fetchJson('/api/v1/agents/') as Promise<AgentType[]>,
      fetchJson('/api/v1/projects/') as Promise<ProjectType[]>,
    ])
    if (agentsResult.status === 'fulfilled') {
      setAgents([...agentsResult.value].sort((a, b) => a.name.localeCompare(b.name)))
    } else {
      console.error('Error fetching agents', agentsResult.reason)
      setError(agentsResult.reason?.message || 'Unknown error')
    }
    setProjects(projectsResult.status === 'fulfilled' ? projectsResult.value : [])
    setLoading(false)
  }, [fetchJson])

  React.useEffect(() => {
    fetchAgents()
  }, [fetchAgents])

  // drop a selected project that is no longer configured
  React.useEffect(() => {
    if (project && !projects.some((p) => p.path === project)) setProject('')
  }, [projects, project])

  const inProject = React.useCallback(
    (a: AgentType) => !project || projectOfAgent(a, projects) === project,
    [project, projects],
  )
  const scopeCounts = React.useMemo(() => {
    const counts: Record<ScopeFilter, number> = { all: 0, global: 0, user: 0, project: 0 }
    agents.filter(inProject).forEach((a) => {
      counts.all++
      if (a.scope) counts[a.scope]++
    })
    return counts
  }, [agents, inProject])
  const visibleAgents = agents.filter((a) => (scope === 'all' || a.scope === scope) && inProject(a))

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div role="tablist" aria-label="Agent scope" className="flex gap-1 rounded-lg bg-muted p-1">
          {SCOPE_TABS.map(({ id, label }) => (
            <button key={id} type="button" role="tab" aria-selected={scope === id} onClick={() => setScope(id)}
                    className={cn('flex cursor-pointer items-center gap-1.5 rounded-md px-2.5 py-1 text-sm transition-colors',
                      scope === id ? 'bg-background font-medium text-foreground shadow-xs' : 'text-muted-foreground hover:text-foreground')}>
              {label}
              <span className="text-xs text-muted-foreground">{scopeCounts[id]}</span>
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          {projects.length > 0 && (
            <label className="flex items-center gap-1.5 text-sm text-muted-foreground">
              <FolderIcon size={14} aria-hidden />
              <span className="sr-only">Project</span>
              <select value={project} onChange={(e) => setProject(e.target.value)} className={selectClass}
                      title={project || 'All projects'}>
                <option value="">All projects</option>
                {projects.map((p) => (
                  <option key={p.path} value={p.path}>{p.path}{p.trusted ? '' : ' (untrusted)'}</option>
                ))}
              </select>
            </label>
          )}
          <Button size="sm" variant="ghost" onClick={fetchAgents} disabled={loading}>
            <RefreshCwIcon className={loading ? 'animate-spin' : ''} /> Refresh
          </Button>
        </div>
      </div>

      {!loading && !error && (
        <p className="text-sm text-muted-foreground">
          {visibleAgents.length === agents.length
            ? `${agents.length} agent${agents.length === 1 ? '' : 's'} configured`
            : `${visibleAgents.length} of ${agents.length} agents`}
        </p>
      )}

      {error && (
        <div className="rounded-lg border border-destructive/50 p-4 text-sm text-destructive">
          Failed to load agents: {error}
        </div>
      )}

      {loading && agents.length === 0 && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {[0, 1, 2].map((i) => <AgentCardSkeleton key={i} />)}
        </div>
      )}

      {!loading && !error && agents.length === 0 && (
        <p className="text-sm text-muted-foreground">No agents found. Create a new agent to get started.</p>
      )}

      {agents.length > 0 && visibleAgents.length === 0 && (
        <p className="text-sm text-muted-foreground">No agents match the selected scope and project.</p>
      )}

      {visibleAgents.length > 0 && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {visibleAgents.map((agent) => <AgentCard key={agent.name} agent={agent} />)}
        </div>
      )}
    </div>
  )
}

export default AgentsView
