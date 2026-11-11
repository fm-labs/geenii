import * as React from 'react'
import {
  ActivityIcon, BotIcon, CheckIcon, ChevronRightIcon, CopyIcon, CpuIcon, FolderIcon, HardDriveIcon, MemoryStickIcon, PackageIcon,
  RefreshCwIcon, TagIcon, TerminalIcon, UserIcon, VariableIcon, XIcon,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge.tsx'
import { Button } from '@/components/ui/button.tsx'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.tsx'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible.tsx'
import { Skeleton } from '@/components/ui/skeleton.tsx'
import JsonView from '@/components/json-view.tsx'
import { useApi } from '@/context/api-context.tsx'
import { cn } from 'cn'

/** Response of GET /info, see `get_app_info()` in geenii/g.py */
type SystemInfo = {
  app: {
    version: string
    cwd: string
    user_home_dir: string
    geenii_user_home_dir: string
    geenii_working_dir: string
    cache_dir: string
  }
  providers: { name: string, configured: boolean }[]
  system: {
    system: {
      boot_time: number
      cpu_count: number
      cpu_percent: number
      cpu_loadavg: number[]
      cpu_loadavg_perc: number[]
      mem_virt: { total: number, available: number, used: number, percent: number }
      mem_swap: { total: number, used: number, percent: number }
    }
    // psutil namedtuple, serialized as [total, used, free, percent]
    disk_usage: Record<string, [number, number, number, number] | null>
    user: Record<string, string | number | (string | number)[] | null>
    binaries: Record<string, string | null>
    env?: Record<string, string>
  }
}

const fmtBytes = (n: number) => {
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let i = 0
  while (n >= 1024 && i < units.length - 1) {
    n /= 1024
    i++
  }
  return `${n.toFixed(i < 2 ? 0 : 1)} ${units[i]}`
}

const fmtUptime = (bootTime: number) => {
  const s = Math.max(0, Date.now() / 1000 - bootTime)
  const d = Math.floor(s / 86400)
  const h = Math.floor((s % 86400) / 3600)
  const m = Math.floor((s % 3600) / 60)
  return d ? `${d}d ${h}h` : h ? `${h}h ${m}m` : `${m}m`
}

const Meter = ({ percent }: { percent: number }) => (
  <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-muted">
    <div className={cn('h-full rounded-full transition-all', percent >= 90 ? 'bg-destructive' : percent >= 75 ? 'bg-amber-500' : 'bg-primary')}
         style={{ width: `${Math.min(100, Math.max(0, percent))}%` }} />
  </div>
)

const Kpi = ({ icon: Icon, label, value, hint, percent }: {
  icon: React.ElementType
  label: string
  value: React.ReactNode
  hint?: React.ReactNode
  percent?: number
}) => (
  <Card className="gap-1 py-4">
    <CardHeader className="px-4">
      <CardDescription className="flex items-center gap-1.5"><Icon size={14} /> {label}</CardDescription>
    </CardHeader>
    <CardContent className="px-4">
      <div className="text-2xl font-semibold tabular-nums">{value}</div>
      {percent !== undefined && <Meter percent={percent} />}
      {hint && <div className="mt-1 text-xs text-muted-foreground">{hint}</div>}
    </CardContent>
  </Card>
)

const Section = ({ icon: Icon, title, description, className, children }: {
  icon: React.ElementType
  title: string
  description?: React.ReactNode
  className?: string
  children: React.ReactNode
}) => (
  <Card className={cn('gap-3', className)}>
    <CardHeader>
      <CardTitle className="flex items-center gap-2 text-base"><Icon size={16} className="text-muted-foreground" /> {title}</CardTitle>
      {description && <CardDescription>{description}</CardDescription>}
    </CardHeader>
    <CardContent>{children}</CardContent>
  </Card>
)

const CopyButton = ({ value }: { value: string }) => {
  const [copied, setCopied] = React.useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value)
      setCopied(true)
      setTimeout(() => setCopied(false), 1200)
    } catch (err) {
      console.error('Copy failed', err)
    }
  }
  return (
    <Button size="icon" variant="ghost" className="size-6 shrink-0 opacity-0 group-hover:opacity-100 focus-visible:opacity-100"
            onClick={copy} title="Copy">
      {copied ? <CheckIcon className="size-3.5" /> : <CopyIcon className="size-3.5" />}
    </Button>
  )
}

/** Key/value rows; values are shown monospaced and copyable */
const KeyValueList = ({ rows }: { rows: [string, React.ReactNode, string?][] }) => (
  <dl className="divide-y text-sm">
    {rows.map(([key, value, copy]) => (
      <div key={key} className="group grid grid-cols-[minmax(7rem,1fr)_minmax(0,2.5fr)] items-center gap-3 py-1.5">
        <dt className="text-muted-foreground">{key}</dt>
        <dd className="flex min-w-0 items-center gap-1">
          <span className="truncate font-mono text-xs" title={copy}>{value}</span>
          {copy && <CopyButton value={copy} />}
        </dd>
      </div>
    ))}
  </dl>
)

const strValue = (v: unknown) => Array.isArray(v) ? v.join(', ') : v === null || v === undefined ? '—' : String(v)

const Expandable = ({ title, children }: { title: string, children: React.ReactNode }) => {
  const [open, setOpen] = React.useState(false)
  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger asChild>
        <Button variant="ghost" size="sm" className="-ml-2 text-muted-foreground">
          <ChevronRightIcon className={cn('transition-transform', open && 'rotate-90')} /> {title}
        </Button>
      </CollapsibleTrigger>
      <CollapsibleContent className="pt-2">{children}</CollapsibleContent>
    </Collapsible>
  )
}

/** Response of GET /api/v1/daemon/status, see geenii/server/daemon_routes.py */
type DaemonStatus = {
  running: boolean
  socket: string
  error: string | null
  info: {
    pid: number
    socket: string
    uptime_s: number
    pm: { running: number }
    scheduler: { status: string, config: string | null, tasks: number, running_tasks: number }
    supervisor: { config: string | null, desired: number, running: number }
  } | null
}

const fmtSeconds = (s: number) => fmtUptime(Date.now() / 1000 - s)

/** Status of the geenii daemon (process manager, scheduler, supervisor) */
const DaemonStatusSection = ({ refreshKey }: { refreshKey: number }) => {
  const { fetchJson } = useApi()
  const [status, setStatus] = React.useState<DaemonStatus | null>(null)
  const [error, setError] = React.useState<string | null>(null)

  React.useEffect(() => {
    let cancelled = false
    fetchJson('/api/v1/daemon/status')
      .then((data: DaemonStatus) => {
        if (cancelled) return
        setStatus(data)
        setError(null)
      })
      .catch((err) => {
        if (cancelled) return
        console.error('Error fetching daemon status:', err)
        setError(err?.message || 'Unknown error')
      })
    return () => { cancelled = true }
  }, [fetchJson, refreshKey])

  const info = status?.info
  const badge = error
    ? <Badge variant="outline" className="text-destructive">unknown</Badge>
    : !status
      ? <Skeleton className="h-5 w-16" />
      : (
        <Badge variant={status.running ? 'secondary' : 'outline'} className="gap-1.5">
          <span className={cn('size-1.5 rounded-full', status.running ? 'bg-emerald-500' : 'bg-destructive')} />
          {status.running ? 'running' : 'not running'}
        </Badge>
      )

  return (
    <Section icon={ActivityIcon} title="Daemon"
             description={<span className="flex items-center gap-2">Process manager, scheduler and supervisor {badge}</span>}>
      {error && <div className="text-sm text-destructive">Failed to load daemon status: {error}</div>}
      {status && !status.running && (
        <div className="flex flex-col gap-2 text-sm text-muted-foreground">
          <span>{status.error}</span>
          <KeyValueList rows={[['Socket', status.socket, status.socket]]} />
        </div>
      )}
      {info && (
        <KeyValueList rows={[
          ['PID', String(info.pid), String(info.pid)],
          ['Uptime', fmtSeconds(info.uptime_s)],
          ['Socket', info.socket, info.socket],
          ['Processes', `${info.pm.running} running`],
          ['Scheduler', `${info.scheduler.status} · ${info.scheduler.tasks} task(s), ${info.scheduler.running_tasks} running`],
          ['Services', `${info.supervisor.running} of ${info.supervisor.desired} running`],
        ]} />
      )}
    </Section>
  )
}

const SystemInfoView = () => {
  const { api } = useApi()
  const [refreshKey, setRefreshKey] = React.useState(0)
  const [data, setData] = React.useState<SystemInfo | null>(null)
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)

  const fetchInfo = React.useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setData(await api.getInfo())
    } catch (err) {
      console.error('Error fetching system info:', err)
      setError(err?.message || 'Unknown error')
    } finally {
      setLoading(false)
    }
  }, [api])

  React.useEffect(() => {
    fetchInfo()
  }, [fetchInfo])

  const refresh = () => {
    setRefreshKey((k) => k + 1)
    fetchInfo()
  }

  const sys = data?.system?.system
  const disk = data?.system?.disk_usage?.['/']
  const binaries = Object.entries(data?.system?.binaries ?? {})
  const foundBinaries = binaries.filter(([, path]) => path).length
  const env = Object.entries(data?.system?.env ?? {}).sort(([a], [b]) => a.localeCompare(b))
  const configuredProviders = data?.providers?.filter((p) => p.configured).length ?? 0

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-end">
        <Button size="sm" variant="ghost" onClick={refresh} disabled={loading}>
          <RefreshCwIcon className={loading ? 'animate-spin' : ''} /> Refresh
        </Button>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/50 p-4 text-sm text-destructive">
          Failed to load system information: {error}
        </div>
      )}

      {!data && loading && (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-28 rounded-xl" />)}
          <Skeleton className="h-64 rounded-xl sm:col-span-2" />
          <Skeleton className="h-64 rounded-xl sm:col-span-2" />
        </div>
      )}

      {data && (
        <div className={cn('flex flex-col gap-4 transition-opacity', loading && 'opacity-60')}>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Kpi icon={TagIcon} label="Geenii" value={`v${data.app?.version ?? '?'}`}
                 hint={sys ? `System up ${fmtUptime(sys.boot_time)}` : undefined} />
            {sys && (
              <Kpi icon={CpuIcon} label="CPU" value={`${Math.round(sys.cpu_percent)}%`} percent={sys.cpu_percent}
                   hint={`${sys.cpu_count} cores · load ${sys.cpu_loadavg.map((l) => l.toFixed(2)).join(' / ')}`} />
            )}
            {sys && (
              <Kpi icon={MemoryStickIcon} label="Memory" value={`${Math.round(sys.mem_virt.percent)}%`} percent={sys.mem_virt.percent}
                   hint={`${fmtBytes(sys.mem_virt.total - sys.mem_virt.available)} of ${fmtBytes(sys.mem_virt.total)} · swap ${fmtBytes(sys.mem_swap.used)}`} />
            )}
            {disk && (
              <Kpi icon={HardDriveIcon} label="Disk /" value={`${Math.round(disk[3])}%`} percent={disk[3]}
                   hint={`${fmtBytes(disk[2])} free of ${fmtBytes(disk[0])}`} />
            )}
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <DaemonStatusSection refreshKey={refreshKey} />

            <Section icon={FolderIcon} title="Directories">
              <KeyValueList rows={([
                ['Working dir', data.app.geenii_working_dir],
                ['Cache dir', data.app.cache_dir],
                ['Home dir', data.app.geenii_user_home_dir],
                ['Process cwd', data.app.cwd],
              ] as [string, string][]).map(([k, v]) => [k, v, v])} />
            </Section>

            <Section icon={BotIcon} title="AI providers" description={`${configuredProviders} of ${data.providers?.length ?? 0} configured`}>
              <div className="flex flex-wrap gap-2">
                {data.providers?.map((p) => (
                  <Badge key={p.name} variant={p.configured ? 'secondary' : 'outline'}
                         className={cn('gap-1.5 py-1', !p.configured && 'text-muted-foreground')}>
                    <span className={cn('size-1.5 rounded-full', p.configured ? 'bg-emerald-500' : 'bg-muted-foreground/40')} />
                    {p.name}
                  </Badge>
                ))}
              </div>
            </Section>

            <Section icon={UserIcon} title="User">
              <KeyValueList rows={Object.entries(data.system?.user ?? {}).map(([k, v]) => [k, strValue(v), strValue(v)])} />
            </Section>

            <Section icon={PackageIcon} title="Binaries" description={`${foundBinaries} of ${binaries.length} found on PATH`}>
              <ul className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm sm:grid-cols-3">
                {binaries.map(([name, path]) => (
                  <li key={name} className="flex items-center gap-1.5" title={path ?? 'Not found'}>
                    {path
                      ? <CheckIcon className="size-3.5 shrink-0 text-emerald-500" />
                      : <XIcon className="size-3.5 shrink-0 text-muted-foreground/50" />}
                    <span className={cn('font-mono text-xs', !path && 'text-muted-foreground line-through decoration-muted-foreground/40')}>{name}</span>
                  </li>
                ))}
              </ul>
            </Section>
          </div>

          {env.length > 0 && (
            <Section icon={VariableIcon} title="Environment" description={`${env.length} variables`}>
              <Expandable title="Show variables">
                <KeyValueList rows={env.map(([k, v]) => [k, v, v])} />
              </Expandable>
            </Section>
          )}

          <Section icon={TerminalIcon} title="Raw data">
            <Expandable title="Show JSON">
              <JsonView src={data} />
            </Expandable>
          </Section>
        </div>
      )}
    </div>
  )
}

export default SystemInfoView
