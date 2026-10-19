import * as React from 'react'
import {
  BotIcon, BoxIcon, BracesIcon, CheckIcon, ChevronRightIcon, CloudIcon, CopyIcon, CpuIcon, HardDriveIcon,
  LayersIcon, ListIcon, RefreshCwIcon, SearchIcon, SparklesIcon, TagIcon, XIcon,
} from 'lucide-react'
import { AiModelInfo } from '@/api/xai.types.ts'
import { agentUrl, AgentType } from '@/app/agents/agent-types.ts'
import { AgentDescription, capText, CountChip, Empty, Section } from '@/app/console/components/agents-settings-view.tsx'
import JsonView from '@/components/json-view.tsx'
import { Badge } from '@/components/ui/badge.tsx'
import { Button } from '@/components/ui/button.tsx'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card.tsx'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible.tsx'
import { Input } from '@/components/ui/input.tsx'
import { Skeleton } from '@/components/ui/skeleton.tsx'
import { useApi } from '@/context/api-context.tsx'
import { modelId, useModels } from '@/hooks/use-models.ts'
import { cn } from 'cn'

type Locality = AiModelInfo['locality']
type LocalityFilter = 'all' | Locality

const LOCALITY: Record<Locality, { label: string, icon: React.ElementType }> = {
  local: { label: 'Local', icon: HardDriveIcon },
  cloud: { label: 'Cloud', icon: CloudIcon },
  mixed: { label: 'Mixed', icon: LayersIcon },
}

const LocalityBadge = ({ locality }: { locality: Locality }) => {
  const { label, icon: Icon } = LOCALITY[locality] || LOCALITY.mixed
  return <Badge variant="outline" className="gap-1"><Icon size={12} /> {label}</Badge>
}

/** Provider descriptions are generic ("OpenAI model x"), so only show ones that add something */
const usefulDescription = (model: AiModelInfo) => {
  const text = model.description?.trim()
  return text && !text.toLowerCase().endsWith(` model ${model.name}`.toLowerCase()) ? text : null
}

const formatValue = (value: unknown) => {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

const CopyButton = ({ text }: { text: string }) => {
  const [copied, setCopied] = React.useState(false)
  const copy = async () => {
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }
  return (
    <Button size="icon" variant="ghost" className="size-6" onClick={copy} title="Copy model id">
      {copied ? <CheckIcon /> : <CopyIcon />}
    </Button>
  )
}

const ModelDetails = ({ model, agents, onClose }: { model: AiModelInfo, agents: AgentType[], onClose: () => void }) => {
  const [showRaw, setShowRaw] = React.useState(false)
  const id = modelId(model)
  const capabilities = model.capabilities || []
  const metadata = Object.entries(model.metadata || {})
  const usedBy = agents.filter((a) => a.model === id)

  return (
    <Card className="gap-4">
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <CardTitle className="flex items-center gap-2">
              <CpuIcon size={16} className="shrink-0" /> <span className="truncate">{model.name}</span>
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
        {usefulDescription(model) && <AgentDescription description={model.description} />}
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="flex min-w-0 items-center gap-0.5 rounded-md bg-muted px-2 py-0.5 font-mono text-xs">
            <span className="truncate" title={id}>{id}</span> <CopyButton text={id} />
          </span>
          <LocalityBadge locality={model.locality} />
          {model.locality === 'local' && (
            <Badge variant={model.installed ? 'secondary' : 'outline'}>{model.installed ? 'Installed' : 'Not installed'}</Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-5">
        {showRaw ? (
          <JsonView src={model} className="max-w-full" />
        ) : (
          <>
            <Section icon={SparklesIcon} title="Capabilities" count={capabilities.length}>
              {capabilities.length === 0
                ? <Empty>The provider doesn't report capabilities for this model.</Empty>
                : (
                  <div className="flex flex-wrap gap-1">
                    {capabilities.map((c) => <Badge key={c} variant="outline" className="font-mono">{c}</Badge>)}
                  </div>
                )}
            </Section>
            <Section icon={BotIcon} title="Used by" count={usedBy.length}>
              {usedBy.length === 0
                ? <Empty>No agent uses this model.</Empty>
                : (
                  <div className="flex flex-wrap gap-1">
                    {usedBy.map((a) => (
                      <a key={a.name} href={agentUrl(a.name)}>
                        <Badge variant="secondary" className="hover:bg-secondary/70">{a.label || a.name}</Badge>
                      </a>
                    ))}
                  </div>
                )}
            </Section>
            <Section icon={TagIcon} title="Metadata" count={metadata.length}>
              {metadata.length === 0
                ? <Empty>No metadata.</Empty>
                : (
                  <dl className="grid grid-cols-[max-content_minmax(0,1fr)] gap-x-4 gap-y-1 text-sm">
                    {metadata.map(([key, value]) => (
                      <React.Fragment key={key}>
                        <dt className="font-mono text-muted-foreground">{key}</dt>
                        <dd className="font-mono break-all">{formatValue(value)}</dd>
                      </React.Fragment>
                    ))}
                  </dl>
                )}
            </Section>
          </>
        )}
      </CardContent>
    </Card>
  )
}

const ProviderGroup = ({ provider, models, selectedId, onSelect, forceOpen }: {
  provider: string
  models: AiModelInfo[]
  selectedId: string | null
  onSelect: (id: string) => void
  forceOpen: boolean
}) => {
  const [open, setOpen] = React.useState(true)
  const localities = [...new Set(models.map((m) => m.locality))]
  return (
    <Collapsible open={open || forceOpen} onOpenChange={setOpen} className="rounded-md border">
      <CollapsibleTrigger className="group flex w-full cursor-pointer items-center gap-2 px-3 py-2 text-left hover:bg-muted/50">
        <ChevronRightIcon size={14} className="shrink-0 transition-transform group-data-[state=open]:rotate-90" />
        <BoxIcon size={16} className="shrink-0" />
        <span className="flex-1 truncate text-sm font-medium">{provider}</span>
        <span className="flex shrink-0 items-center gap-2 text-xs text-muted-foreground">
          {localities.map((l) => {
            const { label, icon } = LOCALITY[l] || LOCALITY.mixed
            return <CountChip key={l} icon={icon} count={models.filter((m) => m.locality === l).length} label={label.toLowerCase()} />
          })}
          <span>{models.length} model{models.length === 1 ? '' : 's'}</span>
        </span>
      </CollapsibleTrigger>
      <CollapsibleContent className="flex flex-col border-t">
        {models.map((model) => {
          const id = modelId(model)
          const description = usefulDescription(model)
          const caps = model.capabilities || []
          return (
            <button key={id} type="button"
                    className={cn('flex w-full cursor-pointer items-start gap-3 border-l-2 border-transparent px-3 py-1.5 pl-9 text-left hover:bg-muted/50',
                      id === selectedId && 'border-primary bg-muted')}
                    onClick={() => onSelect(id)}>
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2 text-sm">
                  <span className="truncate font-mono">{model.name}</span>
                  <span className="flex shrink-0 items-center gap-1">
                    {caps.slice(0, 3).map((c) => (
                      <Badge key={c} variant="outline" className="px-1.5 py-0 text-[10px] font-normal">{c.replace(/_/g, ' ')}</Badge>
                    ))}
                    {caps.length > 3 && <span className="text-xs text-muted-foreground">+{caps.length - 3}</span>}
                    {model.locality === 'local' && model.installed && (
                      <span title="Installed"><CheckIcon size={12} className="text-muted-foreground" /></span>
                    )}
                  </span>
                </div>
                {description && <p className="line-clamp-1 text-xs text-muted-foreground" title={description}>{capText(description)}</p>}
              </div>
            </button>
          )
        })}
      </CollapsibleContent>
    </Collapsible>
  )
}

const ModelsAdminView = () => {
  const { fetchJson } = useApi()
  const { models, loading, error, reload } = useModels()
  const [agents, setAgents] = React.useState<AgentType[]>([])
  const [filter, setFilter] = React.useState('')
  const [locality, setLocality] = React.useState<LocalityFilter>('all')
  const [selectedId, setSelectedId] = React.useState<string | null>(null)

  React.useEffect(() => {
    // only used for "Used by"; the overview works without it
    (fetchJson('/api/v1/agents/') as Promise<AgentType[]>).then(setAgents).catch(() => setAgents([]))
  }, [fetchJson])

  const filtered = React.useMemo(() => {
    const q = filter.trim().toLowerCase()
    return models.filter((m) => (locality === 'all' || m.locality === locality)
      && (!q || [modelId(m), m.description, ...(m.capabilities || [])].some((v) => v?.toLowerCase().includes(q))))
  }, [models, filter, locality])

  const groups = React.useMemo(() => {
    const byProvider = new Map<string, AiModelInfo[]>()
    for (const m of filtered) byProvider.set(m.provider, [...(byProvider.get(m.provider) || []), m])
    return [...byProvider.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([provider, list]) => [provider, [...list].sort((a, b) => a.name.localeCompare(b.name))] as const)
  }, [filtered])

  const localityCounts = React.useMemo(() => {
    const counts: Partial<Record<Locality, number>> = {}
    for (const m of models) counts[m.locality] = (counts[m.locality] || 0) + 1
    return counts
  }, [models])

  const selected = models.find((m) => modelId(m) === selectedId) || null
  const providerCount = new Set(models.map((m) => m.provider)).size

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative w-full max-w-xs">
            <SearchIcon size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <Input className="pl-8" placeholder="Filter models ..." value={filter} onChange={(e) => setFilter(e.target.value)} />
          </div>
          <div className="flex items-center rounded-md border p-0.5">
            {(['all', 'local', 'cloud', 'mixed'] as const)
              .filter((l) => l === 'all' || localityCounts[l])
              .map((l) => (
                <Button key={l} size="sm" variant={locality === l ? 'secondary' : 'ghost'} className="h-7"
                        onClick={() => setLocality(l)} aria-pressed={locality === l}>
                  {l === 'all' ? 'All' : LOCALITY[l].label}
                  <span className="text-xs text-muted-foreground">{l === 'all' ? models.length : localityCounts[l]}</span>
                </Button>
              ))}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground whitespace-nowrap">
            {!loading && !error && `${models.length} model${models.length === 1 ? '' : 's'} from ${providerCount} provider${providerCount === 1 ? '' : 's'}`}
          </span>
          <Button size="sm" variant="ghost" onClick={reload} disabled={loading}>
            <RefreshCwIcon className={loading ? 'animate-spin' : ''} /> Refresh
          </Button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/50 p-4 text-sm text-destructive">
          Failed to load models: {error}
        </div>
      )}

      <div className={cn('grid gap-6', selected && 'lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]')}>
        <div className="flex min-w-0 flex-col gap-2">
          {loading && models.length === 0 && [0, 1, 2].map((i) => <Skeleton key={i} className="h-10 w-full rounded-md" />)}
          {!loading && !error && groups.length === 0 && (
            <p className="text-sm text-muted-foreground">
              {filter || locality !== 'all' ? 'No models match the filter.' : 'No models available. Configure a provider to see its models.'}
            </p>
          )}
          {groups.map(([provider, list]) => (
            <ProviderGroup key={provider} provider={provider} models={list} selectedId={selectedId}
                           forceOpen={!!filter.trim()}
                           onSelect={(id) => setSelectedId(id === selectedId ? null : id)} />
          ))}
        </div>

        {selected && (
          <div className="lg:sticky lg:top-20 lg:self-start">
            <ModelDetails key={selectedId} model={selected} agents={agents} onClose={() => setSelectedId(null)} />
          </div>
        )}
      </div>
    </div>
  )
}

export const ModelsSettingsView = () => <ModelsAdminView />
