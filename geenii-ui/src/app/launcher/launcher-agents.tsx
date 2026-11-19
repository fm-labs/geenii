import React from 'react'
import { Popover as PopoverPrimitive } from 'radix-ui'
import {
  BrainIcon, FolderIcon, InfoIcon, PlugIcon, SettingsIcon, SparklesIcon, StarIcon, WrenchIcon,
} from 'lucide-react'
import { cn } from 'cn'
import { Badge } from '@/components/ui/badge.tsx'
import { Button } from '@/components/ui/button.tsx'
import { Skeleton } from '@/components/ui/skeleton.tsx'
import { agentConfigUrl, agentUrl, AgentType, shortToolName } from '@/app/agents/agent-types.ts'
import { ModelProviderIcon } from '@/app/agents/model-provider.tsx'
import {
  AgentIcon, AgentsEmpty, AgentsError, agentTitle, LauncherAgentsTabProps, visibleAgents,
} from '@/app/launcher/launcher-agents-shared.tsx'

const HOVER_OPEN_DELAY = 450
const HOVER_CLOSE_DELAY = 150

const DetailRow = ({ icon, label, children }: React.PropsWithChildren<{ icon: React.ReactNode, label: string }>) => (
  <div className="flex items-start gap-2">
    <span className="mt-0.5 text-muted-foreground" title={label} aria-label={label}>{icon}</span>
    <div className="flex min-w-0 flex-1 flex-wrap gap-1">{children}</div>
  </div>
)

const AgentDetails = ({ agent, isStarred, onToggleStar }: {
  agent: AgentType
  isStarred: boolean
  onToggleStar: () => void
}) => {
  const tools = agent.tools || []
  const skills = agent.skills || []
  const mcpServers = agent.mcp_servers || []

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-start gap-3">
        <AgentIcon agent={agent} />
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <h3 className="truncate font-semibold leading-tight">{agentTitle(agent)}</h3>
            <button
              type="button"
              onClick={onToggleStar}
              className="-mr-1 -mt-1 rounded-full p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
              title={isStarred ? 'Remove bookmark':'Bookmark'}
            >
              <StarIcon size={16} className={cn(isStarred && 'fill-amber-400 text-amber-400')} />
            </button>
          </div>
          {agent.label && <p className="truncate font-mono text-xs text-muted-foreground">{agent.name}</p>}
          {agent.scope && <Badge variant="secondary" className="mt-1">{agent.scope}</Badge>}
        </div>
      </div>

      <p className="line-clamp-4 text-sm text-muted-foreground">
        {agent.description?.trim() || <span className="italic">No description</span>}
      </p>

      <div className="flex flex-col gap-2 text-xs">
        {agent.model && (
          <DetailRow icon={<BrainIcon size={14} />} label="Model">
            <span className="flex min-w-0 items-center gap-1.5">
              <ModelProviderIcon model={agent.model} size={16} />
              <span className="truncate font-mono">{agent.model}</span>
            </span>
          </DetailRow>
        )}
        {tools.length > 0 && (
          <DetailRow icon={<WrenchIcon size={14} />} label="Tools">
            {tools.slice(0, 6).map((t) => <Badge key={t} variant="outline" title={t}>{shortToolName(t)}</Badge>)}
            {tools.length > 6 && <Badge variant="outline" title={tools.slice(6).join('\n')}>+{tools.length - 6}</Badge>}
          </DetailRow>
        )}
        {skills.length > 0 && (
          <DetailRow icon={<SparklesIcon size={14} />} label="Skills">
            {skills.map((s) => <Badge key={s}>{s}</Badge>)}
          </DetailRow>
        )}
        {mcpServers.length > 0 && (
          <DetailRow icon={<PlugIcon size={14} />} label="MCP servers">
            {mcpServers.map((s) => <Badge key={s} variant="secondary">{s}</Badge>)}
          </DetailRow>
        )}
        {agent.working_dir && (
          <DetailRow icon={<FolderIcon size={14} />} label="Working directory">
            <span className="truncate font-mono" title={agent.working_dir}>{agent.working_dir}</span>
          </DetailRow>
        )}
      </div>

      <div className="flex gap-2">
        <Button asChild size="sm" className="flex-1">
          <a href={agentUrl(agent.name)}>Launch</a>
        </Button>
        <Button asChild size="sm" variant="outline" title="Configure">
          <a href={agentConfigUrl(agent.name)}><SettingsIcon /></a>
        </Button>
      </div>
    </div>
  )
}

const AgentTile = ({ agent, isStarred, onToggleStar }: {
  agent: AgentType
  isStarred: boolean
  onToggleStar: () => void
}) => {
  const [open, setOpen] = React.useState(false)
  // pinned = opened by clicking the info button; stays open until dismissed
  const [pinned, setPinned] = React.useState(false)
  const timer = React.useRef<ReturnType<typeof setTimeout>>(undefined)

  const schedule = (fn: () => void, delay: number) => {
    clearTimeout(timer.current)
    timer.current = setTimeout(fn, delay)
  }
  React.useEffect(() => () => clearTimeout(timer.current), [])

  const onHoverStart = () => {
    if (!pinned) schedule(() => setOpen(true), open ? 0:HOVER_OPEN_DELAY)
  }
  const onHoverEnd = () => {
    if (!pinned) schedule(() => setOpen(false), HOVER_CLOSE_DELAY)
  }

  const onOpenChange = (next: boolean) => {
    clearTimeout(timer.current)
    setOpen(next)
    if (!next) setPinned(false)
  }

  const onInfoClick = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    clearTimeout(timer.current)
    const next = !(open && pinned)
    setPinned(next)
    setOpen(next)
  }

  return (
    <PopoverPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <PopoverPrimitive.Anchor asChild>
        <div
          className="group relative flex w-36 flex-col items-center"
          onMouseEnter={onHoverStart}
          onMouseLeave={onHoverEnd}
        >
          <a
            href={agentUrl(agent.name)}
            className="flex max-w-full flex-col items-center gap-2 rounded-2xl p-2 outline-none focus-visible:ring-2 focus-visible:ring-ring"
            title={agentTitle(agent)}
          >
            <AgentIcon agent={agent} />
            <span className="line-clamp-2 max-w-full text-center text-sm leading-tight break-words">
              {agentTitle(agent)}
            </span>
          </a>
          <button
            type="button"
            onClick={onInfoClick}
            aria-label={`Details for ${agentTitle(agent)}`}
            className={cn(
              'absolute rounded-full border bg-background p-0.5 text-muted-foreground shadow-sm',
              'opacity-0 transition-opacity group-hover:opacity-100 focus-visible:opacity-100 hover:text-foreground',
              'top-0.5 right-1.5',
              open && pinned && 'opacity-100 text-foreground',
            )}
          >
            <InfoIcon size={14} />
          </button>
          {isStarred && (
            <StarIcon size={12} className="absolute top-1 left-2 fill-amber-400 text-amber-400"
                      aria-label="Bookmarked" />
          )}
        </div>
      </PopoverPrimitive.Anchor>
      <PopoverPrimitive.Portal>
        <PopoverPrimitive.Content
          side="bottom"
          sideOffset={6}
          collisionPadding={16}
          onOpenAutoFocus={(e) => e.preventDefault()}
          onMouseEnter={onHoverStart}
          onMouseLeave={onHoverEnd}
          className={cn(
            'z-1100 w-80 rounded-2xl border bg-popover/95 p-4 text-popover-foreground shadow-xl backdrop-blur-md outline-none',
            'data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95',
            'data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95',
          )}
        >
          <AgentDetails agent={agent} isStarred={isStarred} onToggleStar={onToggleStar} />
        </PopoverPrimitive.Content>
      </PopoverPrimitive.Portal>
    </PopoverPrimitive.Root>
  )
}

const TileSkeleton = () => (
  <div className="flex w-36 flex-col items-center gap-2 p-2">
    <Skeleton className="size-24 rounded-[26px]" />
    <Skeleton className="h-3 w-14" />
  </div>
)

/** The launcher's agents tab: icon tiles with a details popover, filtered by the launcher search */
const LauncherAgents = ({ agents, loading, error, query, starred, toggleStar }: LauncherAgentsTabProps) => {
  const visible = visibleAgents(agents, query, starred)

  return <>
    {error && <AgentsError error={error} />}

    {loading && (
      <section className="flex w-full flex-wrap justify-center gap-x-4 gap-y-6">
        {[0, 1, 2, 3, 4, 5].map((i) => <TileSkeleton key={i} />)}
      </section>
    )}

    {!loading && visible.length > 0 && (
      <section role="tabpanel" className="flex w-full flex-wrap justify-center gap-x-4 gap-y-6">
        {visible.map((agent) => (
          <AgentTile
            key={agent.name}
            agent={agent}
            isStarred={starred.includes(agent.name)}
            onToggleStar={() => toggleStar(agent.name)}
          />
        ))}
      </section>
    )}

    {!loading && !error && visible.length===0 && (
      <AgentsEmpty query={query} emptyText="No agents configured yet." />
    )}
  </>
}

export default LauncherAgents
