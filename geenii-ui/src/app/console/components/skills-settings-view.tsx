import * as React from 'react'
import {
  BotIcon, BracesIcon, FileCodeIcon, ListIcon, RefreshCwIcon, ScrollTextIcon, SearchIcon,
  SparklesIcon, TagIcon, WrenchIcon, XIcon, ZapIcon,
} from 'lucide-react'
import { agentUrl } from '@/app/agents/agent-types.ts'
import { AgentDescription, capText, CountChip, Empty, Section } from '@/app/console/components/agents-settings-view.tsx'
import JsonView from '@/components/json-view.tsx'
import { OutputDataMarkdown } from '@/components/output-data-markdown.tsx'
import { markdownClass } from '@/components/xchat/parts/media-parts.tsx'
import { Badge } from '@/components/ui/badge.tsx'
import { Button } from '@/components/ui/button.tsx'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card.tsx'
import { Input } from '@/components/ui/input.tsx'
import { Skeleton } from '@/components/ui/skeleton.tsx'
import { useApi } from '@/context/api-context.tsx'
import { cn } from 'cn'

/** GET /api/v1/skills/: one entry per skill in the app's skill registry */
type SkillType = {
  name: string
  path: string
  source: string
  description: string
  triggers: string[]
  allowed_tools: string[]
  metadata: Record<string, any>
  scripts: string[]
  used_by: string[]
}

/** GET /api/v1/skills/{name}: the summary plus the markdown body of SKILL.md */
type SkillDetailType = SkillType & { instructions: string }

const BadgeList = ({ items, empty, mono = true }: { items: string[], empty: string, mono?: boolean }) => (
  items.length === 0
    ? <Empty>{empty}</Empty>
    : <div className="flex flex-wrap gap-1">{items.map((i) => <Badge key={i} variant="outline" className={cn(mono && 'font-mono')}>{i}</Badge>)}</div>
)

const SkillConfigDetails = ({ skill, onClose }: { skill: SkillType, onClose: () => void }) => {
  const { fetchJson } = useApi()
  const [detail, setDetail] = React.useState<SkillDetailType | null>(null)
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)
  const [showRaw, setShowRaw] = React.useState(false)

  React.useEffect(() => {
    let cancelled = false
    ;(fetchJson(`/api/v1/skills/${encodeURIComponent(skill.name)}`) as Promise<SkillDetailType>)
      .then((data) => { if (!cancelled) setDetail(data) })
      .catch((err) => { if (!cancelled) setError(err?.message || 'Unknown error') })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [fetchJson, skill.name])

  const metadata = Object.entries(skill.metadata || {})
  const instructions = detail?.instructions?.trim()

  return (
    <Card className="gap-4">
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <CardTitle className="flex items-center gap-2">
              <SparklesIcon size={16} className="shrink-0" /> <span className="truncate">{skill.name}</span>
            </CardTitle>
          </div>
          <div className="flex shrink-0 items-center gap-1">
            <Button size="sm" variant="ghost" onClick={() => setShowRaw(!showRaw)} aria-pressed={showRaw}
                    title={showRaw ? 'Show details' : 'Show raw JSON'}>
              {showRaw ? <ListIcon /> : <BracesIcon />} {showRaw ? 'Details' : 'Raw JSON'}
            </Button>
            <Button size="icon" variant="ghost" onClick={onClose} title="Close">
              <XIcon />
            </Button>
          </div>
        </div>
        <AgentDescription description={skill.description} />
        <p className="truncate font-mono text-xs text-muted-foreground" title={skill.path}>{skill.path}</p>
      </CardHeader>
      <CardContent className="flex flex-col gap-5">
        {error && (
          <div className="rounded-lg border border-destructive/50 p-3 text-sm text-destructive">
            Failed to load skill details: {error}
          </div>
        )}
        {showRaw ? (
          <JsonView src={detail || skill} className="max-w-full" />
        ) : (
          <>
            <Section icon={ZapIcon} title="Triggers" count={skill.triggers.length}>
              <BadgeList items={skill.triggers} empty="No triggers; the skill is only activated with /<skill> or by the model." />
            </Section>
            <Section icon={WrenchIcon} title="Allowed tools" count={skill.allowed_tools.length}>
              <BadgeList items={skill.allowed_tools} empty="No tool restrictions." />
            </Section>
            <Section icon={FileCodeIcon} title="Scripts" count={skill.scripts.length}>
              <BadgeList items={skill.scripts} empty="No scripts." />
              {skill.scripts.length > 0 && (
                <p className="mt-1 text-xs text-muted-foreground">
                  Executable scripts become tools named <code className="font-mono">{skill.name}__&lt;script&gt;</code>.
                </p>
              )}
            </Section>
            <Section icon={BotIcon} title="Used by" count={skill.used_by.length}>
              {skill.used_by.length === 0
                ? <Empty>No agent lists this skill.</Empty>
                : (
                  <div className="flex flex-wrap gap-1">
                    {skill.used_by.map((a) => (
                      <a key={a} href={agentUrl(a)}><Badge variant="secondary" className="hover:bg-secondary/70">{a}</Badge></a>
                    ))}
                  </div>
                )}
            </Section>
            {metadata.length > 0 && (
              <Section icon={TagIcon} title="Metadata" count={metadata.length} defaultOpen={false}>
                <dl className="grid grid-cols-[max-content_minmax(0,1fr)] gap-x-4 gap-y-1 text-sm">
                  {metadata.map(([key, value]) => (
                    <React.Fragment key={key}>
                      <dt className="font-mono text-muted-foreground">{key}</dt>
                      <dd className="font-mono break-all">{typeof value === 'object' ? JSON.stringify(value) : String(value)}</dd>
                    </React.Fragment>
                  ))}
                </dl>
              </Section>
            )}
            <Section icon={ScrollTextIcon} title="Instructions" defaultOpen={false}>
              {loading && <Skeleton className="h-24 w-full" />}
              {!loading && !instructions && <Empty>SKILL.md has no instructions.</Empty>}
              {instructions && (
                <div className={cn('max-h-96 overflow-auto rounded-md border p-3 text-sm', markdownClass)}>
                  <OutputDataMarkdown data={instructions} />
                </div>
              )}
            </Section>
          </>
        )}
      </CardContent>
    </Card>
  )
}

const SkillsAdminView = () => {
  const { fetchJson } = useApi()
  const [skills, setSkills] = React.useState<SkillType[]>([])
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)
  const [filter, setFilter] = React.useState('')
  const [selectedName, setSelectedName] = React.useState<string | null>(null)

  const fetchSkills = React.useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setSkills(await fetchJson('/api/v1/skills/'))
    } catch (err) {
      console.error('Error fetching skills', err)
      setError(err?.message || 'Unknown error')
    } finally {
      setLoading(false)
    }
  }, [fetchJson])

  React.useEffect(() => {
    fetchSkills()
  }, [fetchSkills])

  const filtered = React.useMemo(() => {
    const q = filter.trim().toLowerCase()
    return skills.filter((s) => !q || [s.name, s.description, ...s.triggers]
      .some((v) => v?.toLowerCase().includes(q)))
  }, [skills, filter])

  const selected = skills.find((s) => s.name === selectedName) || null

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-2">
        <div className="relative w-full max-w-xs">
          <SearchIcon size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input className="pl-8" placeholder="Filter skills ..." value={filter} onChange={(e) => setFilter(e.target.value)} />
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground whitespace-nowrap">
            {!loading && !error && `${skills.length} skill${skills.length === 1 ? '' : 's'}`}
          </span>
          <Button size="sm" variant="ghost" onClick={fetchSkills} disabled={loading}>
            <RefreshCwIcon className={loading ? 'animate-spin' : ''} /> Refresh
          </Button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/50 p-4 text-sm text-destructive">
          Failed to load skills: {error}
        </div>
      )}

      <div className={cn('grid gap-6', selected && 'lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]')}>
        <div className="flex min-w-0 flex-col gap-2">
          {loading && skills.length === 0 && [0, 1, 2].map((i) => <Skeleton key={i} className="h-14 w-full rounded-md" />)}
          {!loading && !error && filtered.length === 0 && (
            <p className="text-sm text-muted-foreground">{filter ? 'No skills match the filter.' : 'No skills found in the skill directories.'}</p>
          )}
          {filtered.map((skill) => (
            <button key={skill.name} type="button"
                    className={cn('flex w-full cursor-pointer items-start gap-3 rounded-md border px-3 py-2 text-left hover:bg-muted/50',
                      skill.name === selectedName && 'border-primary bg-muted')}
                    onClick={() => setSelectedName(skill.name === selectedName ? null : skill.name)}>
              <SparklesIcon size={16} className="mt-0.5 shrink-0" />
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2 text-sm font-medium">
                  <span className="truncate font-mono">{skill.name}</span>
                  <span className="flex shrink-0 items-center gap-2 text-xs font-normal text-muted-foreground">
                    <CountChip icon={ZapIcon} count={skill.triggers.length} label="triggers" />
                    <CountChip icon={FileCodeIcon} count={skill.scripts.length} label="scripts" />
                    <CountChip icon={BotIcon} count={skill.used_by.length} label="agents" />
                  </span>
                </div>
                <p className="line-clamp-2 text-xs text-muted-foreground" title={skill.description?.trim()}>
                  {capText(skill.description) || <span className="italic">No description</span>}
                </p>
              </div>
            </button>
          ))}
        </div>

        {selected && (
          <div className="lg:sticky lg:top-20 lg:self-start">
            {/* keyed by name, so details are fetched once per selected skill */}
            <SkillConfigDetails key={selected.name} skill={selected} onClose={() => setSelectedName(null)} />
          </div>
        )}
      </div>
    </div>
  )
}

export const SkillsSettingsView = () => <SkillsAdminView />
