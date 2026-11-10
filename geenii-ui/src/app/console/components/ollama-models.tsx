import React from 'react'

import { Input } from '@/components/ui/input.tsx'
import { BrainIcon, ChevronDownIcon, CloudIcon, DownloadIcon, HardDriveIcon, CheckIcon, CopyIcon, ExternalLinkIcon, PackageIcon, TagIcon, ClockIcon, EyeIcon, LayersIcon, WrenchIcon } from 'lucide-react'
import { cn } from 'cn'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog.tsx'
import { Button } from '@/components/ui/button.tsx'
import { Badge } from '@/components/ui/badge.tsx'

/**
 * OllamaModels Component
 * Renders a list of Ollama models.
 *
 * Example Model data:
 *   {
 *     "name": "nemotron-3-nano",
 *     "description": "Nemotron 3 Nano - A new Standard for Efficient, Open, and Intelligent Agentic Models",
 *     "pulls": "81.3K",
 *     "tag_count": "6",
 *     "sizes": [
 *       "30b"
 *     ],
 *     "capabilities": [
 *       "tools",
 *       "thinking"
 *     ],
 *     "updated": "2025-12-16 06:27:00",
 *     "tags": [
 *       {
 *         "name": "nemotron-3-nano:latest",
 *         "size": "24GB",
 *         "context_window": "1M",
 *         "input_type": "Text"
 *       }
 *     ]
 *  }
 *
 * @returns {JSX.Element} The OllamaModels component.
 * @constructor
 */
type OllamaModelTag = {
  name: string
  size: string | null
  context_window: string
  input_type: string
  cloud?: boolean
}

type OllamaModel = {
  name: string
  description: string
  pulls: string
  tag_count: string
  sizes: string[]
  capabilities: string[]
  updated: string
  tags: OllamaModelTag[]
}

// "cloud" is not a capability in the catalog, it's derived from the tags
const CAPABILITIES: { key: string, label: string, icon: React.ElementType }[] = [
  { key: 'tools', label: 'Tools', icon: WrenchIcon },
  { key: 'vision', label: 'Vision', icon: EyeIcon },
  { key: 'thinking', label: 'Thinking', icon: BrainIcon },
  { key: 'embedding', label: 'Embedding', icon: LayersIcon },
  { key: 'cloud', label: 'Cloud', icon: CloudIcon },
]

// parameter count buckets, in billions
const PARAM_BUCKETS: { key: string, label: string, min: number, max: number }[] = [
  { key: 'tiny', label: '< 1B', min: 0, max: 1 },
  { key: 'small', label: '1–4B', min: 1, max: 4.5 },
  { key: 'medium', label: '4–15B', min: 4.5, max: 15 },
  { key: 'large', label: '15–40B', min: 15, max: 40 },
  { key: 'xl', label: '40–100B', min: 40, max: 100 },
  { key: 'huge', label: '100B+', min: 100, max: Infinity },
]

// max download size options, in GB
const DOWNLOAD_LIMITS = [1, 2, 4, 8, 16, 32, 64]

/** "7b" -> 7, "270m" -> 0.27, "8x7b" -> 56, "e2b" -> 2 (billions of parameters) */
const parseParamSize = (size: string): number | null => {
  const m = size.toLowerCase().match(/^e?(?:(\d+(?:\.\d+)?)x)?(\d+(?:\.\d+)?)([mb])$/)
  if (!m) return null
  const n = parseFloat(m[2]) * (m[1] ? parseFloat(m[1]) : 1)
  return m[3] === 'm' ? n / 1000 : n
}

/** "24GB" -> 24, "301MB" -> 0.301 (gigabytes) */
const parseDiskSize = (size: string | null): number | null => {
  const m = size?.match(/^(\d+(?:\.\d+)?)\s*(KB|MB|GB|TB)$/i)
  if (!m) return null
  const factor = { KB: 1e-6, MB: 1e-3, GB: 1, TB: 1000 }[m[2].toUpperCase() as 'KB' | 'MB' | 'GB' | 'TB']
  return parseFloat(m[1]) * factor
}

/** "81.3K" -> 81300 */
const parsePulls = (pulls: string): number => {
  const m = pulls?.match(/^(\d+(?:\.\d+)?)([KMB]?)$/i)
  if (!m) return 0
  return parseFloat(m[1]) * ({ '': 1, K: 1e3, M: 1e6, B: 1e9 }[m[2].toUpperCase() as '' | 'K' | 'M' | 'B'])
}

// newer catalogs set `cloud` per tag; older ones only hint it in the tag name
const isCloudTag = (tag: OllamaModelTag) =>
  typeof tag.cloud === 'boolean' ? tag.cloud : tag.name.toLowerCase().includes('cloud')

const modelHasCloudTag = (model: OllamaModel) => model.tags.some(isCloudTag)

const modelHasCapability = (model: OllamaModel, cap: string) =>
  cap === 'cloud' ? modelHasCloudTag(model) : model.capabilities.includes(cap)

/** smallest local (non-cloud) download, in GB */
const smallestDownload = (model: OllamaModel): number | null => {
  const sizes = model.tags.filter((t) => !isCloudTag(t)).map((t) => parseDiskSize(t.size)).filter((n): n is number => n !== null)
  return sizes.length ? Math.min(...sizes) : null
}

/** A shell command with a copy button */
const CommandLine = ({ command }: { command: string }) => {
  const [copied, setCopied] = React.useState(false)

  const copy = () => {
    navigator.clipboard?.writeText(command).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    }).catch((err) => console.error('Failed to copy to clipboard:', err))
  }

  return (
    <div className={'flex items-center gap-2 rounded-md border bg-muted px-3 py-1.5'}>
      <code className={'flex-1 font-mono text-sm [overflow-wrap:anywhere]'}>
        <span className={'select-none text-muted-foreground'}>$ </span>{command}
      </code>
      <Button variant={'ghost'} size={'icon-xs'} title={copied ? 'Copied' : 'Copy'} onClick={copy}>
        {copied ? <CheckIcon /> : <CopyIcon />}
      </Button>
    </div>
  )
}

/** Explains how to install a model tag with the ollama cli */
const OllamaInstallDialog = ({ tag, onClose }: { tag: OllamaModelTag | null, onClose: () => void }) => (
  <Dialog open={tag !== null} onOpenChange={(open) => !open && onClose()}>
    <DialogContent className={'sm:max-w-lg'}>
      {tag && (
        <>
          <DialogHeader>
            <DialogTitle>Install {tag.name}</DialogTitle>
            <DialogDescription>
              Models are installed with the Ollama command line tool.
              {tag.size && <> This tag is a <strong>{tag.size}</strong> download.</>}
            </DialogDescription>
          </DialogHeader>
          <ol className={'space-y-4 text-sm'}>
            <li className={'space-y-1.5'}>
              <div><span className={'font-medium'}>1. Install Ollama</span>, if you haven't yet:</div>
              <a href={'https://ollama.com/download'} target={'_blank'} rel={'noreferrer'}
                 className={'inline-flex items-center gap-1 text-primary underline-offset-4 hover:underline'}>
                ollama.com/download <ExternalLinkIcon className={'size-3.5'} />
              </a>
            </li>
            <li className={'space-y-1.5'}>
              <div><span className={'font-medium'}>2. Download the model</span> in a terminal:</div>
              <CommandLine command={`ollama pull ${tag.name}`} />
            </li>
            <li className={'space-y-1.5'}>
              <div><span className={'font-medium'}>3. Check it's installed:</span></div>
              <CommandLine command={'ollama list'} />
            </li>
            <li className={'space-y-1.5'}>
              <div><span className={'font-medium'}>4. Try it out</span> (optional):</div>
              <CommandLine command={`ollama run ${tag.name}`} />
            </li>
          </ol>
          <DialogFooter>
            <Button variant={'outline'} onClick={onClose}>Close</Button>
          </DialogFooter>
        </>
      )}
    </DialogContent>
  </Dialog>
)

type SortKey = 'popular' | 'updated' | 'name'

const selectClassName = 'border-input dark:bg-input/30 h-9 rounded-md border bg-transparent px-3 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px]'

const OllamaModels = () => {
  const [searchTerm, setSearchTerm] = React.useState('')
  const [activeModel, setActiveModel] = React.useState<string | null>(null)
  const [capFilter, setCapFilter] = React.useState<Set<string>>(new Set())
  const [paramFilter, setParamFilter] = React.useState<string>('')
  const [maxDownload, setMaxDownload] = React.useState<number>(0)
  const [installTag, setInstallTag] = React.useState<OllamaModelTag | null>(null)
  const [sortBy, setSortBy] = React.useState<SortKey>('popular')

  const [modelData, setModelData] = React.useState<OllamaModel[]>([])

  const toggleCap = (cap: string) => {
    setCapFilter((prev) => {
      const next = new Set(prev)
      if (next.has(cap)) next.delete(cap)
      else next.add(cap)
      return next
    })
  }

  const capCounts = React.useMemo(() => {
    const counts: Record<string, number> = {}
    CAPABILITIES.forEach(({ key }) => {
      counts[key] = modelData.filter((m) => modelHasCapability(m, key)).length
    })
    return counts
  }, [modelData])

  const hasFilters = searchTerm.trim() !== '' || capFilter.size > 0 || paramFilter !== '' || maxDownload > 0

  const resetFilters = () => {
    setSearchTerm('')
    setCapFilter(new Set())
    setParamFilter('')
    setMaxDownload(0)
  }

  const filteredModels = React.useMemo(() => {
    const term = searchTerm.trim().toLowerCase()
    const bucket = PARAM_BUCKETS.find((b) => b.key === paramFilter)

    const result = modelData.filter((model) => {
      // all selected capabilities must be present
      for (const cap of capFilter) {
        if (!modelHasCapability(model, cap)) return false
      }

      // at least one size variant must fall into the bucket
      if (bucket) {
        const inBucket = model.sizes.some((s) => {
          const n = parseParamSize(s)
          return n !== null && n >= bucket.min && n < bucket.max
        })
        if (!inBucket) return false
      }

      // at least one local tag must fit the download limit
      if (maxDownload > 0) {
        const smallest = smallestDownload(model)
        if (smallest === null || smallest > maxDownload) return false
      }

      if (term) {
        return model.name.toLowerCase().includes(term) ||
          model.description?.toLowerCase().includes(term) ||
          model.capabilities.some((c) => c.includes(term)) ||
          model.tags.some((tag) => tag.name.toLowerCase().includes(term))
      }
      return true
    })

    const sorted = [...result]
    if (sortBy === 'popular') sorted.sort((a, b) => parsePulls(b.pulls) - parsePulls(a.pulls))
    else if (sortBy === 'updated') sorted.sort((a, b) => (b.updated || '').localeCompare(a.updated || ''))
    else sorted.sort((a, b) => a.name.localeCompare(b.name))
    return sorted
  }, [searchTerm, modelData, capFilter, paramFilter, maxDownload, sortBy])

  const fetchModels = React.useCallback(async () => {
    try {
      const response = await fetch('/assets/ollama-model-catalog-20261111.json')
      if (response.ok) {
        const data = await response.json()
        setModelData(data)
      } else {
        console.error('Failed to fetch models:', response.statusText)
      }
    } catch (error) {
      console.error('Error fetching models:', error)
    }
  }, [])

  React.useEffect(() => {
    fetchModels()
  }, [fetchModels])

  return (
    <div>
      <div className={'mb-4 space-y-3'}>
        <div className={'flex flex-wrap gap-2'}>
          <Input className={'flex-1 min-w-48'} placeholder={'Filter models ...'}
                 onChange={(e) => setSearchTerm(e.target.value)} value={searchTerm} />
          <select className={selectClassName} value={paramFilter} title={'Parameter size'}
                  onChange={(e) => setParamFilter(e.target.value)}>
            <option value={''}>Any parameter size</option>
            {PARAM_BUCKETS.map((b) => <option key={b.key} value={b.key}>{b.label} params</option>)}
          </select>
          <select className={selectClassName} value={maxDownload} title={'Smallest local download must fit'}
                  onChange={(e) => setMaxDownload(Number(e.target.value))}>
            <option value={0}>Any download size</option>
            {DOWNLOAD_LIMITS.map((gb) => <option key={gb} value={gb}>≤ {gb} GB download</option>)}
          </select>
          <select className={selectClassName} value={sortBy} title={'Sort by'}
                  onChange={(e) => setSortBy(e.target.value as SortKey)}>
            <option value={'popular'}>Most pulled</option>
            <option value={'updated'}>Recently updated</option>
            <option value={'name'}>Name</option>
          </select>
        </div>
        <div className={'flex flex-wrap items-center gap-1.5'}>
          {CAPABILITIES.map(({ key, label, icon: Icon }) => (
            <Button key={key} size={'xs'} variant={capFilter.has(key) ? 'default' : 'outline'}
                    className={'rounded-full'} onClick={() => toggleCap(key)} aria-pressed={capFilter.has(key)}>
              <Icon />
              {label}
              <span className={'opacity-60'}>{capCounts[key]}</span>
            </Button>
          ))}
          {hasFilters && (
            <Button size={'xs'} variant={'ghost'} className={'text-muted-foreground'} onClick={resetFilters}>
              Clear filters
            </Button>
          )}
          <span className={'ml-auto text-xs text-muted-foreground'}>
            {filteredModels.length} of {modelData.length} models
          </span>
        </div>
      </div>
      <div className={'space-y-3'}>
        {filteredModels.map((model) => {
          const isActive = activeModel === model.name
          const smallest = smallestDownload(model)
          const cloudTagCount = model.tags.filter(isCloudTag).length
          const localTagCount = model.tags.length - cloudTagCount
          return (
            <div key={model.name}
                 className={cn(
                   'rounded-lg border bg-card p-4 transition-colors hover:border-foreground/20 hover:bg-accent/40',
                   isActive && 'border-foreground/20 bg-accent/30',
                 )}>
              <button type={'button'} className={'w-full text-left cursor-pointer'}
                      onClick={() => setActiveModel(isActive ? null : model.name)} aria-expanded={isActive}>
                <div className={'flex items-start justify-between gap-2 mb-1'}>
                  <h3 className={'font-semibold flex flex-wrap items-center gap-1.5'}>
                    {model.name}
                    {localTagCount > 0 && (
                      <Badge variant={'secondary'} className={'font-normal'} title={`${localTagCount} local tag(s)`}>
                        <HardDriveIcon />local <span className={'opacity-60'}>{localTagCount}</span>
                      </Badge>
                    )}
                    {cloudTagCount > 0 && (
                      <Badge variant={'secondary'} className={'font-normal'} title={`${cloudTagCount} cloud tag(s)`}>
                        <CloudIcon />cloud <span className={'opacity-60'}>{cloudTagCount}</span>
                      </Badge>
                    )}
                  </h3>
                  <ChevronDownIcon className={cn('size-4 shrink-0 mt-1 text-muted-foreground transition-transform', isActive && 'rotate-180')} />
                </div>
                <p className={'text-sm text-muted-foreground mb-3'}>{model.description}</p>
                <div className={'flex flex-wrap items-center gap-1.5 text-xs'}>
                  {model.capabilities.map((cap) => {
                    const Icon = CAPABILITIES.find((c) => c.key === cap)?.icon
                    return (
                      <Badge key={cap} variant={'outline'} className={'font-normal'}>
                        {Icon && <Icon />}{cap}
                      </Badge>
                    )
                  })}
                  {model.sizes.map((size) => (
                    <Badge key={size} variant={'secondary'} className={'font-mono font-normal'}>{size}</Badge>
                  ))}
                  <span className={'ml-auto flex flex-wrap items-center gap-x-3 text-muted-foreground [&>span]:inline-flex [&>span]:items-center [&>span]:gap-1 [&_svg]:size-3.5'}>
                    <span title={'Pulls'}><DownloadIcon />{model.pulls}</span>
                    {smallest !== null && <span title={'Smallest local download'}><PackageIcon />from {smallest < 1 ? `${Math.round(smallest * 1000)}MB` : `${smallest}GB`}</span>}
                    <span title={'Tags'}><TagIcon />{model.tag_count}</span>
                    {model.updated && <span title={model.updated}><ClockIcon />{model.updated.slice(0, 10)}</span>}
                  </span>
                </div>
              </button>
              {isActive && (
                <div className={'mt-4 overflow-x-auto'}>
                  <table className={'w-full text-sm'}>
                    <thead className={'text-xs text-muted-foreground border-b'}>
                      <tr>
                        <th className={'py-1.5 text-left font-medium'}>Tag</th>
                        <th className={'py-1.5 ps-4 text-right font-medium'}>Size</th>
                        <th className={'py-1.5 ps-4 text-right font-medium'}>Context</th>
                        <th className={'py-1.5 ps-4 text-right font-medium'}>Input</th>
                        <th className={'py-1.5 ps-4 text-right font-medium'}>Install</th>
                      </tr>
                    </thead>
                    <tbody>
                      {model.tags.map((tag) => (
                        <tr key={tag.name} className={'border-b last:border-0 hover:bg-muted/50'}>
                          <td className={'py-1 font-mono text-xs'}>{tag.name}</td>
                          <td className={'py-1 ps-4 text-right'}>{tag.size ?? '—'}</td>
                          <td className={'py-1 ps-4 text-right'}>{tag.context_window}</td>
                          <td className={'py-1 ps-4 text-right'}>{tag.input_type}</td>
                          <td className={'py-1 ps-4 text-right'}>
                            {!isCloudTag(tag) ? <Button title={`Install ${tag.name}`} variant={'ghost'} size={'icon-sm'}
                                      onClick={() => setInstallTag(tag)}>
                              <DownloadIcon />
                            </Button> : ''}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )
        })}
        {modelData.length > 0 && filteredModels.length === 0 && (
          <div className={'rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground'}>
            No models match these filters.
          </div>
        )}
      </div>
      <OllamaInstallDialog tag={installTag} onClose={() => setInstallTag(null)} />
    </div>
  )
}

export default OllamaModels
