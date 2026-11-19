import React from 'react'
import { Popover as PopoverPrimitive } from 'radix-ui'
import {
  BrainIcon, FolderIcon, InfoIcon, PlugIcon, SearchIcon, SettingsIcon, SparklesIcon, StarIcon, WrenchIcon,
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card.tsx'
import { cn } from 'cn'
import { Badge } from '@/components/ui/badge.tsx'
import { Button } from '@/components/ui/button.tsx'
import { Skeleton } from '@/components/ui/skeleton.tsx'
import { useApi } from '@/context/api-context.tsx'
import { agentUrl, AgentType, shortToolName } from '@/app/agents/agent-types.ts'
import { ModelProviderIcon } from '@/app/agents/model-provider.tsx'
import { useApps } from '@/app/apps/apps-api.ts'
import LauncherApps, { appPageUrl, matchesAppQuery } from '@/app/launcher/launcher-apps.tsx'

/** Agents starred until the user decides otherwise */
const DEFAULT_STARRED = ['default']
const STARRED_STORAGE_KEY = 'geenii.launcher.starred'

const HOVER_OPEN_DELAY = 450
const HOVER_CLOSE_DELAY = 150

const useStarredAgents = () => {
  const [starred, setStarred] = React.useState<string[]>(() => {
    try {
      const stored = localStorage.getItem(STARRED_STORAGE_KEY)
      return stored ? JSON.parse(stored):DEFAULT_STARRED
    } catch {
      return DEFAULT_STARRED
    }
  })

  const toggleStar = React.useCallback((name: string) => {
    setStarred((prev) => {
      const next = prev.includes(name) ? prev.filter((n) => n!==name):[...prev, name]
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
  const initials = words.length > 1 ? words[0][0] + words[1][0]:agentTitle(agent).slice(0, 2)
  return initials.toUpperCase()
}

const AgentIcon = ({ agent, size = 'lg' }: { agent: AgentType, size?: 'sm' | 'lg' }) => {
  const hue = agentHue(agent.name)
  return (
    <div
      className={cn(
        'relative flex items-center justify-center font-semibold text-white select-none',
        'shadow-[0_1px_2px_rgba(0,0,0,0.15),0_4px_12px_rgba(0,0,0,0.08)]',
        'transition-transform duration-200 ease-out group-active:scale-95',
        size==='lg'
          ? 'size-24 rounded-[26px] text-3xl group-hover:scale-[1.06]'
          :'size-11 shrink-0 rounded-[13px] text-base',
      )}
      style={{
        background: `linear-gradient(145deg, hsl(${hue} 75% 62%), hsl(${(hue + 35) % 360} 70% 45%))`,
      }}
    >
      {agentInitials(agent)}
      <ModelProviderIcon
        model={agent.model}
        size={size==='lg' ? 26:18}
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
              <button
                type="button"
                onClick={onToggleStar}
                className="relative z-10 -mt-1 -mr-1 rounded-full p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                title={isStarred ? 'Remove bookmark':'Bookmark'}
              >
                <StarIcon size={16} className={cn(isStarred && 'fill-amber-400 text-amber-400')} />
              </button>
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

const TileSkeleton = () => (
  <div className="flex w-36 flex-col items-center gap-2 p-2">
    <Skeleton className="size-24 rounded-[26px]" />
    <Skeleton className="h-3 w-14" />
  </div>
)

type LauncherTab = 'agents' | 'project' | 'apps'

const TABS: { id: LauncherTab, label: string }[] = [
  { id: 'agents', label: 'Agents' },
  { id: 'apps', label: 'Apps' },
  { id: 'project', label: 'Project' },
]

const tabOf = (agent: AgentType): Exclude<LauncherTab, 'apps'> => (agent.scope==='project' ? 'project':'agents')

const matchesQuery = (agent: AgentType, query: string) => {
  const q = query.trim().toLowerCase()
  if (!q) return true
  return [agent.name, agent.label, agent.description, agent.model]
    .some((v) => v?.toLowerCase().includes(q))
}

const LauncherView = () => {

  const searchParams = new URLSearchParams(window.location.search)
  const tabParam = searchParams.get('tab')

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

  const [tab, setTab] = React.useState<LauncherTab>('agents')
  React.useEffect(() => {
     console.log("TAB", window.location.search, tabParam)
     setTab(tabParam as LauncherTab)
  }, [tabParam])

  // polled only while the apps tab is shown; disabled apps aren't launchable, so they're left out
  const appsState = useApps(tab==='apps')
  const apps = React.useMemo(
    () => appsState.data
      ? appsState.data.apps.filter((a) => a.enabled).sort((a, b) => a.title.localeCompare(b.title))
      :null,
    [appsState.data],
  )

  // the list was loaded once on mount: refresh it when switching to the apps tab
  const reloadApps = appsState.reload
  React.useEffect(() => {
    if (tab==='apps') reloadApps(true)
  }, [tab, reloadApps])

  const tabCounts = React.useMemo(() => {
    const counts: Record<LauncherTab, number> = { agents: 0, project: 0, apps: apps?.length ?? 0 }
    agents.forEach((a) => {
      counts[tabOf(a)]++
    })
    return counts
  }, [agents, apps])

  // bookmarked agents first, then alphabetical (agents are already sorted by title)
  const filtered = agents
    .filter((a) => tabOf(a)===tab && matchesQuery(a, query))
    .sort((a, b) => Number(starred.includes(b.name)) - Number(starred.includes(a.name)))

  const onSearchKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key==='Enter' && tab==='apps') {
      const first = apps?.find((a) => matchesAppQuery(a, query))
      if (first) window.location.hash = appPageUrl(first)
    } else if (e.key==='Enter' && filtered.length > 0) {
      window.location.hash = agentUrl(filtered[0].name).slice(1)
    } else if (e.key==='Escape') {
      setQuery('')
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-[70vw] flex-col items-center gap-8 pt-6 pb-10">
      <div
        role="tablist"
        aria-label="Agent scope"
        className="inline-flex items-center gap-1 rounded-full border bg-muted/50 p-1"
      >
        {TABS.map(({ id, label }) => {
          const active = tab===id
          return (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => setTab(id)}
              className={cn(
                'flex items-center gap-2 rounded-full px-4 py-1.5 text-sm font-medium outline-none transition',
                'focus-visible:ring-2 focus-visible:ring-ring',
                active
                  ? 'bg-background text-foreground shadow-sm'
                  :'text-muted-foreground hover:text-foreground',
              )}
            >
              {label}
              {(id==='apps' ? apps!==null:!loading) && (
                <span
                  className={cn('text-xs tabular-nums', active ? 'text-muted-foreground':'text-muted-foreground/70')}>
                  {tabCounts[id]}
                </span>
              )}
            </button>
          )
        })}
      </div>

      <div className="relative w-full max-w-sm">
        <SearchIcon size={16} className="absolute top-1/2 left-3.5 -translate-y-1/2 text-muted-foreground" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={onSearchKeyDown}
          placeholder={tab==='apps' ? 'Search apps':tab==='project' ? 'Search project agents':'Search agents'}
          autoFocus
          className="h-10 w-full rounded-full border bg-muted/50 pr-4 pl-10 text-sm outline-none transition focus:bg-background focus:ring-[3px] focus:ring-ring/40"
        />
      </div>

      {tab==='apps' && (
        <LauncherApps
          apps={apps}
          daemonRunning={!!appsState.data?.daemon.running}
          loading={appsState.loading}
          error={appsState.error}
          query={query}
          reload={appsState.reload}
        />
      )}

      {tab!=='apps' && <>
        {error && (
          <div className="rounded-lg border border-destructive/50 p-4 text-sm text-destructive">
            Failed to load agents: {error}
          </div>
        )}

        {loading && (tab==='project' ? (
          <section className="grid w-full grid-cols-1 gap-4 md:grid-cols-2">
            {[0, 1].map((i) => <CardSkeleton key={i} />)}
          </section>
        ):(
          <section className="flex w-full flex-wrap justify-center gap-x-4 gap-y-6">
            {[0, 1, 2, 3, 4, 5].map((i) => <TileSkeleton key={i} />)}
          </section>
        ))}

        {!loading && filtered.length > 0 && tab==='agents' && (
          <section role="tabpanel" className="flex w-full flex-wrap justify-center gap-x-4 gap-y-6">
            {filtered.map((agent) => (
              <AgentTile
                key={agent.name}
                agent={agent}
                isStarred={starred.includes(agent.name)}
                onToggleStar={() => toggleStar(agent.name)}
              />
            ))}
          </section>
        )}

        {!loading && filtered.length > 0 && tab==='project' && (
          <section role="tabpanel" className="grid w-full grid-cols-1 gap-4 md:grid-cols-2">
            {filtered.map((agent) => (
              <ProjectAgentCard
                key={agent.name}
                agent={agent}
                isStarred={starred.includes(agent.name)}
                onToggleStar={() => toggleStar(agent.name)}
              />
            ))}
          </section>
        )}

        {!loading && !error && filtered.length===0 && (
          <p className="text-sm text-muted-foreground">
            {query
              ? `No agents match “${query}”`
              :tab==='project' ? 'No project agents found.':'No agents configured yet.'}
          </p>
        )}
      </>}
    </div>
  )
}

export default LauncherView
