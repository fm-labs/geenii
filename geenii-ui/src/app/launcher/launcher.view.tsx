import React from 'react'
import { SearchIcon } from 'lucide-react'
import { cn } from 'cn'
import { useApi } from '@/context/api-context.tsx'
import { useNavigate, useRoute } from '@/app-router.tsx'
import { agentUrl, AgentType } from '@/app/agents/agent-types.ts'
import { useApps } from '@/app/apps/apps-api.ts'
import LauncherApps, { appPageUrl, matchesAppQuery } from '@/app/launcher/launcher-apps.tsx'
import LauncherAgents from '@/app/launcher/launcher-agents.tsx'
import LauncherProject from '@/app/launcher/launcher-project.tsx'
import { agentTitle, useStarredAgents, visibleAgents } from '@/app/launcher/launcher-agents-shared.tsx'

type LauncherTab = 'agents' | 'project' | 'apps'

const TABS: { id: LauncherTab, label: string }[] = [
  { id: 'agents', label: 'Agents' },
  { id: 'apps', label: 'Apps' },
  { id: 'project', label: 'Project' },
]

/** Each tab has its own route, so tab switches land in the browser history */
const TAB_PATHS: Record<LauncherTab, string> = {
  agents: '/agents',
  project: '/project',
  apps: '/apps',
}

const tabOfPath = (path: string | undefined): LauncherTab =>
  TABS.find((t) => TAB_PATHS[t.id]===path)?.id ?? 'agents'

const tabOf = (agent: AgentType): Exclude<LauncherTab, 'apps'> => (agent.scope==='project' ? 'project':'agents')

const SEARCH_PLACEHOLDER: Record<LauncherTab, string> = {
  agents: 'Search agents',
  project: 'Search project agents',
  apps: 'Search apps',
}

const LauncherView = () => {

  const route = useRoute()
  const navigate = useNavigate()
  const tab = tabOfPath(route.route?.path)
  const setTab = (next: LauncherTab) => {
    if (next!==tab) navigate(TAB_PATHS[next])
  }

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

  const agentsByTab = React.useMemo(() => ({
    agents: agents.filter((a) => tabOf(a)==='agents'),
    project: agents.filter((a) => tabOf(a)==='project'),
  }), [agents])

  const tabCounts: Record<LauncherTab, number> = {
    agents: agentsByTab.agents.length,
    project: agentsByTab.project.length,
    apps: apps?.length ?? 0,
  }

  const onSearchKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key==='Enter') {
      if (tab==='apps') {
        const first = apps?.find((a) => matchesAppQuery(a, query))
        if (first) window.location.hash = appPageUrl(first)
      } else {
        const first = visibleAgents(agentsByTab[tab], query, starred)[0]
        if (first) window.location.hash = agentUrl(first.name).slice(1)
      }
    } else if (e.key==='Escape') {
      setQuery('')
    }
  }

  const agentsTabProps = { loading, error, query, starred, toggleStar }

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
          placeholder={SEARCH_PLACEHOLDER[tab]}
          autoFocus
          className="h-10 w-full rounded-full border bg-muted/50 pr-4 pl-10 text-sm outline-none transition focus:bg-background focus:ring-[3px] focus:ring-ring/40"
        />
      </div>

      {tab==='agents' && <LauncherAgents agents={agentsByTab.agents} {...agentsTabProps} />}

      {tab==='project' && <LauncherProject agents={agentsByTab.project} {...agentsTabProps} />}

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
    </div>
  )
}

export default LauncherView
