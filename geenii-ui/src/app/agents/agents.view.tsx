import React from 'react'
import { BotIcon, BrainIcon, FileTextIcon, PlugIcon, RefreshCwIcon, SparklesIcon, WrenchIcon } from 'lucide-react'
import { Badge } from '@/components/ui/badge.tsx'
import { Button } from '@/components/ui/button.tsx'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card.tsx'
import { Skeleton } from '@/components/ui/skeleton.tsx'
import { useApi } from '@/context/api-context.tsx'
import { agentUrl, AgentType, shortToolName } from '@/app/agents/agent-types.ts'

const MAX_VISIBLE_TOOLS = 5

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
              {agent.class_name && (
                <Badge variant="secondary" title={agent.class_name}>{agent.class_name.split('.').pop()}</Badge>
              )}
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

      {agent.file_path && (
        <CardFooter className="mt-auto border-t pt-4! text-xs text-muted-foreground">
          <FileTextIcon size={12} className="mr-1 shrink-0" />
          <span className="truncate font-mono" title={agent.file_path}>{agent.file_path}</span>
        </CardFooter>
      )}
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

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {!loading && !error && `${agents.length} agent${agents.length === 1 ? '' : 's'} configured`}
        </p>
        <Button size="sm" variant="ghost" onClick={fetchAgents} disabled={loading}>
          <RefreshCwIcon className={loading ? 'animate-spin' : ''} /> Refresh
        </Button>
      </div>

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

      {agents.length > 0 && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {agents.map((agent) => <AgentCard key={agent.name} agent={agent} />)}
        </div>
      )}
    </div>
  )
}

export default AgentsView
