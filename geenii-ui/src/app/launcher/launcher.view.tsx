import React from 'react'
import { Popover as PopoverPrimitive } from 'radix-ui'
import {
  BrainIcon, FolderIcon, InfoIcon, PlugIcon, SearchIcon, SettingsIcon, SparklesIcon, StarIcon, WrenchIcon,
} from 'lucide-react'
import { cn } from 'cn'
import { Badge } from '@/components/ui/badge.tsx'
import { Button } from '@/components/ui/button.tsx'
import { Skeleton } from '@/components/ui/skeleton.tsx'
import { useApi } from '@/context/api-context.tsx'
import { agentUrl, AgentType, shortToolName } from '@/app/agents/agent-types.ts'
import { ModelProviderIcon } from '@/app/agents/model-provider.tsx'

/** Agents starred until the user decides otherwise */
const DEFAULT_STARRED = ['default']
const STARRED_STORAGE_KEY = 'geenii.launcher.starred'

const HOVER_OPEN_DELAY = 450
const HOVER_CLOSE_DELAY = 150

const useStarredAgents = () => {
  const [starred, setStarred] = React.useState<string[]>(() => {
    try {
      const stored = localStorage.getItem(STARRED_STORAGE_KEY)
      return stored ? JSON.parse(stored) : DEFAULT_STARRED
    } catch {
      return DEFAULT_STARRED
    }
  })

  const toggleStar = React.useCallback((name: string) => {
    setStarred((prev) => {
      const next = prev.includes(name) ? prev.filter((n) => n !== name) : [...prev, name]
      try {
        localStorage.setItem(STARRED_STORAGE_KEY, JSON.stringify(next))
      } catch {
        // storage unavailable: keep the in-memory state only
      }
      return next
    })
  }, [])

  return { starred, toggleStar }
}

/** Deterministic hue per agent, so each icon keeps its color across reloads */
const agentHue = (name: string) => {
  let hash = 0
  for (let i = 0; i < name.length; i++) {
    hash = (hash * 31 + name.charCodeAt(i)) | 0
  }
  return Math.abs(hash) % 360
}

const agentTitle = (agent: AgentType) => agent.label || agent.name

const agentInitials = (agent: AgentType) => {
  const words = agentTitle(agent).split(/[\s_\-.]+/).filter(Boolean)
  const initials = words.length > 1 ? words[0][0] + words[1][0] : agentTitle(agent).slice(0, 2)
  return initials.toUpperCase()
}

const AgentIcon = ({ agent }: { agent: AgentType }) => {
  const hue = agentHue(agent.name)
  return (
    <div
      className={cn(
        'relative flex items-center justify-center font-semibold text-white select-none',
        'shadow-[0_1px_2px_rgba(0,0,0,0.15),0_4px_12px_rgba(0,0,0,0.08)]',
        'transition-transform duration-200 ease-out group-active:scale-95',
        'size-20 rounded-[22px] text-2xl group-hover:scale-[1.06]',
      )}
      style={{
        background: `linear-gradient(145deg, hsl(${hue} 75% 62%), hsl(${(hue + 35) % 360} 70% 45%))`,
      }}
    >
      {agentInitials(agent)}
      <ModelProviderIcon
        model={agent.model}
        size={26}
        className="absolute -right-1 -bottom-1 ring-2 ring-background shadow-sm"
      />
    </div>
  )
}

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
              title={isStarred ? 'Unstar' : 'Star'}
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
          <a href="#/console/configure/agents"><SettingsIcon /></a>
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
    if (!pinned) schedule(() => setOpen(true), open ? 0 : HOVER_OPEN_DELAY)
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
          className="group relative flex w-28 flex-col items-center"
          onMouseEnter={onHoverStart}
          onMouseLeave={onHoverEnd}
        >
          <a
            href={agentUrl(agent.name)}
            className="flex max-w-full flex-col items-center gap-2 rounded-2xl p-2 outline-none focus-visible:ring-2 focus-visible:ring-ring"
            title={agentTitle(agent)}
          >
            <AgentIcon agent={agent} />
            <span className="max-w-full truncate text-center text-sm">
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
            <StarIcon size={12} className="absolute top-1 left-2 fill-amber-400 text-amber-400" aria-label="Starred" />
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
  <div className="flex w-28 flex-col items-center gap-2 p-2">
    <Skeleton className="size-20 rounded-[22px]" />
    <Skeleton className="h-3 w-14" />
  </div>
)

/** Grid sections, broadest scope first; agents without a scope go last */
const SCOPE_GROUPS: { scope: AgentType['scope'], label: string }[] = [
  { scope: 'global', label: 'Global' },
  { scope: 'user', label: 'User' },
  { scope: 'project', label: 'Project' },
  { scope: undefined, label: 'Other' },
]

const matchesQuery = (agent: AgentType, query: string) => {
  const q = query.trim().toLowerCase()
  if (!q) return true
  return [agent.name, agent.label, agent.description, agent.model]
    .some((v) => v?.toLowerCase().includes(q))
}

const LauncherView = () => {
  const { fetchJson } = useApi()
  const { starred, toggleStar } = useStarredAgents()

  const [agents, setAgents] = React.useState<AgentType[]>([])
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)
  const [query, setQuery] = React.useState('')

  React.useEffect(() => {
    fetchJson('/api/v1/agents/')
      .then((data: AgentType[]) => setAgents([...data].sort((a, b) => agentTitle(a).localeCompare(agentTitle(b)))))
      .catch((err) => {
        console.error('Error fetching agents', err)
        setError(err?.message || 'Unknown error')
      })
      .finally(() => setLoading(false))
  }, [fetchJson])

  const filtered = agents.filter((a) => matchesQuery(a, query))

  const onSearchKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && filtered.length > 0) {
      window.location.hash = agentUrl(filtered[0].name).slice(1)
    } else if (e.key === 'Escape') {
      setQuery('')
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col items-center gap-10 pt-6 pb-10">
      <div className="relative w-full max-w-sm">
        <SearchIcon size={16} className="absolute top-1/2 left-3.5 -translate-y-1/2 text-muted-foreground" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={onSearchKeyDown}
          placeholder="Search agents"
          autoFocus
          className="h-10 w-full rounded-full border bg-muted/50 pr-4 pl-10 text-sm outline-none transition focus:bg-background focus:ring-[3px] focus:ring-ring/40"
        />
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/50 p-4 text-sm text-destructive">
          Failed to load agents: {error}
        </div>
      )}


      {loading && (
        <section className="flex w-full flex-wrap justify-center gap-x-4 gap-y-6">
          {[0, 1, 2, 3, 4, 5].map((i) => <TileSkeleton key={i} />)}
        </section>
      )}

      {SCOPE_GROUPS.map(({ scope, label }) => {
        const groupAgents = filtered.filter((a) => (a.scope || undefined) === scope)
        if (groupAgents.length === 0) return null
        return (
          <section key={label} className="flex w-full flex-col gap-4">
            <h2 className="flex items-center gap-3 text-xs font-medium tracking-wider text-muted-foreground uppercase">
              {label}
              <span className="font-normal normal-case tracking-normal">{groupAgents.length}</span>
              <span className="h-px flex-1 bg-border" aria-hidden />
            </h2>
            <div className="flex flex-wrap gap-x-4 gap-y-6">
              {groupAgents.map((agent) => (
                <AgentTile
                  key={agent.name}
                  agent={agent}
                  isStarred={starred.includes(agent.name)}
                  onToggleStar={() => toggleStar(agent.name)}
                />
              ))}
            </div>
          </section>
        )
      })}

      {!loading && !error && filtered.length === 0 && (
        <p className="text-sm text-muted-foreground">
          {query ? `No agents match “${query}”` : 'No agents configured yet.'}
        </p>
      )}
    </div>
  )
}

export default LauncherView
