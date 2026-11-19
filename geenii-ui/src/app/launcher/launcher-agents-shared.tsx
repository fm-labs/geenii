import React from 'react'
import { cn } from 'cn'
import { AgentType } from '@/app/agents/agent-types.ts'
import { ModelProviderIcon } from '@/app/agents/model-provider.tsx'

/** Agents starred until the user decides otherwise */
const DEFAULT_STARRED = ['default']
const STARRED_STORAGE_KEY = 'geenii.launcher.starred'

export const useStarredAgents = () => {
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

/** Props shared by the agent tabs of the launcher */
export type LauncherAgentsTabProps = {
  agents: AgentType[]
  loading: boolean
  error: string | null
  query: string
  starred: string[]
  toggleStar: (name: string) => void
}

export const agentTitle = (agent: AgentType) => agent.label || agent.name

export const matchesAgentQuery = (agent: AgentType, query: string) => {
  const q = query.trim().toLowerCase()
  if (!q) return true
  return [agent.name, agent.label, agent.description, agent.model]
    .some((v) => v?.toLowerCase().includes(q))
}

/** Agents matching the query: bookmarked first, then in the given order */
export const visibleAgents = (agents: AgentType[], query: string, starred: string[]) => agents
  .filter((a) => matchesAgentQuery(a, query))
  .sort((a, b) => Number(starred.includes(b.name)) - Number(starred.includes(a.name)))

/** Deterministic hue per agent, so each icon keeps its color across reloads */
const agentHue = (name: string) => {
  let hash = 0
  for (let i = 0; i < name.length; i++) {
    hash = (hash * 31 + name.charCodeAt(i)) | 0
  }
  return Math.abs(hash) % 360
}

const agentInitials = (agent: AgentType) => {
  const words = agentTitle(agent).split(/[\s_\-.]+/).filter(Boolean)
  const initials = words.length > 1 ? words[0][0] + words[1][0]:agentTitle(agent).slice(0, 2)
  return initials.toUpperCase()
}

export const AgentIcon = ({ agent, size = 'lg' }: { agent: AgentType, size?: 'sm' | 'lg' }) => {
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

export const AgentsError = ({ error }: { error: string }) => (
  <div className="rounded-lg border border-destructive/50 p-4 text-sm text-destructive">
    Failed to load agents: {error}
  </div>
)

export const AgentsEmpty = ({ query, emptyText }: { query: string, emptyText: string }) => (
  <p className="text-sm text-muted-foreground">
    {query ? `No agents match “${query}”`:emptyText}
  </p>
)
