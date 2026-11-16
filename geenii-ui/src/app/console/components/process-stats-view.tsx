import * as React from 'react'
import {
  ActivityIcon, AlertTriangleIcon, ClockIcon, DownloadIcon, HandIcon, RefreshCwIcon, RotateCwIcon, TimerOffIcon,
} from 'lucide-react'
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Badge } from '@/components/ui/badge.tsx'
import { Button } from '@/components/ui/button.tsx'
import { Skeleton } from '@/components/ui/skeleton.tsx'
import { useApi } from '@/context/api-context.tsx'
import { ApiError, readProblem } from '@/api/api-error.ts'
import { cn } from 'cn'
import {
  ChartCard, ChartTooltip, Kpi, RANGES, Segmented, axisProps, color, fmt, fmtDay, fmtDuration, full,
} from '@/app/console/components/usage-stats-view.tsx'
import { processUrl } from '@/app/console/components/process-manager-view.tsx'

/** Counters of GET /api/v1/stats/processes, see COUNTER_FIELDS in geenii/proc_stats.py */
type ProcTotals = {
  runs: number
  completed: number
  failed: number
  killed: number
  timeouts: number
  skipped: number
  restarts: number
  spawn_errors: number
  gave_up: number
  duration_ms: number
  timed_runs: number
  actions: number
  avg_duration_ms: number | null
}

type ProcRow = ProcTotals & { key: string, component?: string, name?: string }

type ProcStats = {
  start: string
  end: string
  first_day: string | null
  last_day: string | null
  totals: ProcTotals
  active_days: number
  daily: (ProcTotals & { date: string })[]
  hourly: number[]
  by_component: ProcRow[]
  by_name: ProcRow[]
}

/** A line of the process event log, see geenii/proc_events.py */
type ProcEvent = {
  ts: string
  component: 'pm' | 'scheduler' | 'supervisor'
  event: string
  name?: string
  run_id?: string
  system_pid?: number
  trigger?: string
  actor?: string
  cmd?: string | string[]
  state?: string
  exit_code?: number
  duration_ms?: number
  error?: string
  [key: string]: unknown
}

type EventFilter = 'all' | 'runs' | 'actions'

const COMPONENTS = ['all', 'pm', 'scheduler', 'supervisor'] as const

const fmtTime = (iso: string) => {
  const d = new Date(iso)
  return isNaN(d.getTime()) ? iso : d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

const STATE_STYLES: Record<string, string> = {
  completed: 'text-emerald-600',
  failed: 'text-destructive',
  killed: 'text-amber-600',
}

const DailyRunsChart = ({ stats }: { stats: ProcStats }) => {
  const data = stats.daily.map((d) => ({ ...d, other: Math.max(0, d.runs - d.completed - d.failed - d.killed) }))
  const series = [
    { key: 'completed', name: 'Completed', color: color(1) },
    { key: 'failed', name: 'Failed', color: 'var(--destructive)' },
    { key: 'killed', name: 'Killed', color: color(3) },
  ]
  return (
    <ChartCard title="Finished runs per day" description={`${fmtDay(stats.start)} – ${fmtDay(stats.end)}`}>
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={data} margin={{ left: 0, right: 8, top: 8 }}>
          <CartesianGrid vertical={false} stroke="var(--border)" />
          <XAxis dataKey="date" {...axisProps} tickFormatter={(d) => fmtDay(d)} minTickGap={24} />
          <YAxis {...axisProps} tickFormatter={fmt} width={44} allowDecimals={false} />
          <Tooltip content={<ChartTooltip labelFormatter={(d) => fmtDay(d, true)} />} cursor={{ fill: 'var(--muted)', opacity: 0.5 }} />
          <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12 }} />
          {series.map((s, i) => (
            <Bar key={s.key} dataKey={s.key} name={s.name} stackId="a" fill={s.color}
                 radius={i === series.length - 1 ? [3, 3, 0, 0] : 0} maxBarSize={36} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}

const ByNameTable = ({ stats }: { stats: ProcStats }) => (
  <ChartCard title="By task / service" description="Runs, failures and restarts per scheduled task, service or plain process">
    {stats.by_name.length === 0 ? <NoData /> : (
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-xs text-muted-foreground">
            <tr className="border-b">
              <th className="py-2 pr-3 text-left font-medium">Name</th>
              <th className="px-3 py-2 text-right font-medium">Runs</th>
              <th className="px-3 py-2 text-right font-medium">Failed</th>
              <th className="px-3 py-2 text-right font-medium">Killed</th>
              <th className="px-3 py-2 text-right font-medium">Timeouts</th>
              <th className="px-3 py-2 text-right font-medium">Restarts</th>
              <th className="px-3 py-2 text-right font-medium">Avg run time</th>
              <th className="py-2 pl-3 text-right font-medium">Actions</th>
            </tr>
          </thead>
          <tbody className="tabular-nums">
            {stats.by_name.map((r) => (
              <tr key={r.key} className="border-b last:border-b-0">
                <td className="max-w-72 py-2 pr-3">
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className="font-normal">{r.component}</Badge>
                    <span className="truncate font-medium" title={r.name}>{r.name}</span>
                  </div>
                </td>
                <td className="px-3 py-2 text-right">{full.format(r.runs)}</td>
                <td className={cn('px-3 py-2 text-right', r.failed && 'text-destructive')}>{full.format(r.failed)}</td>
                <td className="px-3 py-2 text-right">{full.format(r.killed)}</td>
                <td className={cn('px-3 py-2 text-right', r.timeouts && 'text-amber-600')}>{full.format(r.timeouts)}</td>
                <td className={cn('px-3 py-2 text-right', r.restarts && 'text-amber-600')}>{full.format(r.restarts)}</td>
                <td className="px-3 py-2 text-right">{fmtDuration(r.avg_duration_ms)}</td>
                <td className="py-2 pl-3 text-right">{full.format(r.actions)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )}
  </ChartCard>
)

const EventLog = () => {
  const { fetchJson } = useApi()
  const [filter, setFilter] = React.useState<EventFilter>('all')
  const [component, setComponent] = React.useState<(typeof COMPONENTS)[number]>('all')
  const [events, setEvents] = React.useState<ProcEvent[] | null>(null)
  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const load = React.useCallback(async () => {
    setLoading(true)
    setError(null)
    const q = new URLSearchParams({ limit: '300' })
    if (filter !== 'all') q.set('audit', String(filter === 'actions'))
    if (component !== 'all') q.set('component', component)
    try {
      setEvents((await fetchJson(`/api/v1/stats/processes/events?${q}`)).events)
    } catch (err) {
      setError(err?.message || 'Unknown error')
    } finally {
      setLoading(false)
    }
  }, [fetchJson, filter, component])

  React.useEffect(() => {
    load()
  }, [load])

  return (
    <ChartCard title="Event log" description="Newest first: process runs and the control actions behind them (who started, stopped or changed what)"
               actions={
                 <div className="flex flex-wrap items-center gap-2">
                   <Segmented value={filter} onChange={setFilter} options={[
                     { label: 'All', value: 'all' }, { label: 'Runs', value: 'runs' }, { label: 'Actions', value: 'actions' },
                   ]} />
                   <Segmented value={component} onChange={setComponent} options={COMPONENTS.map((c) => ({ label: c === 'all' ? 'Any' : c, value: c }))} />
                   <Button size="sm" variant="ghost" onClick={load} disabled={loading}>
                     <RefreshCwIcon className={loading ? 'animate-spin' : ''} />
                   </Button>
                 </div>
               }>
      {error && <div className="text-sm text-destructive">Failed to load events: {error}</div>}
      {!events && !error && <Skeleton className="h-40 rounded-md" />}
      {events && events.length === 0 && <NoData />}
      {events && events.length > 0 && (
        <div className={cn('max-h-[28rem] overflow-auto transition-opacity', loading && 'opacity-60')}>
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-card text-muted-foreground">
              <tr className="border-b">
                <th className="py-2 pr-3 text-left font-medium">Time</th>
                <th className="px-3 py-2 text-left font-medium">Component</th>
                <th className="px-3 py-2 text-left font-medium">Event</th>
                <th className="px-3 py-2 text-left font-medium">Name / run</th>
                <th className="px-3 py-2 text-left font-medium">Result</th>
                <th className="py-2 pl-3 text-left font-medium">By</th>
              </tr>
            </thead>
            <tbody>
              {events.map((e, i) => {
                const isAction = e.event.includes('.')
                const cmd = Array.isArray(e.cmd) ? e.cmd.join(' ') : e.cmd
                return (
                  <tr key={`${e.ts}-${i}`} className="border-b align-top last:border-b-0">
                    <td className="whitespace-nowrap py-1.5 pr-3 tabular-nums text-muted-foreground" title={e.ts}>{fmtTime(e.ts)}</td>
                    <td className="px-3 py-1.5">{e.component}</td>
                    <td className="px-3 py-1.5">
                      <span className={cn('font-mono', isAction && 'font-medium')}>{e.event}</span>
                      {e.trigger && <span className="ml-1.5 text-muted-foreground">({e.trigger})</span>}
                    </td>
                    <td className="max-w-80 px-3 py-1.5">
                      {e.name && <div className="truncate font-medium" title={e.name}>{e.name}</div>}
                      {/* Runs with an OS pid are process manager processes; callable task runs have none */}
                      {e.run_id && e.system_pid !== undefined
                        ? <a className="block truncate font-mono text-muted-foreground underline-offset-2 hover:underline" href={processUrl(e.run_id)}>{e.run_id}</a>
                        : e.run_id && <div className="truncate font-mono text-muted-foreground">{e.run_id}</div>}
                      {cmd && <div className="truncate font-mono text-muted-foreground" title={cmd}>{cmd}</div>}
                    </td>
                    <td className="px-3 py-1.5">
                      {e.state && <span className={STATE_STYLES[e.state]}>{e.state}</span>}
                      {e.exit_code !== undefined && <span className="ml-1 text-muted-foreground">rc={e.exit_code}</span>}
                      {e.duration_ms !== undefined && <span className="ml-1 text-muted-foreground">{fmtDuration(e.duration_ms)}</span>}
                      {e.backoff_s !== undefined && <span className="text-amber-600">in {String(e.backoff_s)}s</span>}
                      {e.error && <div className="max-w-64 truncate text-destructive" title={e.error}>{e.error}</div>}
                    </td>
                    <td className="py-1.5 pl-3 text-muted-foreground">{e.actor ?? (isAction ? '—' : '')}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </ChartCard>
  )
}

const NoData = () => <p className="py-8 text-center text-sm text-muted-foreground">No process events in this range.</p>

/** Process run statistics and the event log of the process manager, scheduler and supervisor */
export const ProcessStatsView = () => {
  const { fetchJson, fetch } = useApi()
  const [days, setDays] = React.useState<number>(30)
  const [stats, setStats] = React.useState<ProcStats | null>(null)
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)
  const [downloading, setDownloading] = React.useState(false)

  const fetchStats = React.useCallback(async (refresh = false) => {
    setLoading(true)
    setError(null)
    try {
      setStats(await fetchJson(`/api/v1/stats/processes?days=${days}${refresh ? '&refresh=true' : ''}`))
    } catch (err) {
      console.error('Error fetching process stats', err)
      setError(err?.message || 'Unknown error')
    } finally {
      setLoading(false)
    }
  }, [fetchJson, days])

  React.useEffect(() => {
    fetchStats()
  }, [fetchStats])

  // Fetched (not linked), so the request carries the API's auth like every other call
  const downloadCsv = async () => {
    setDownloading(true)
    try {
      const res = await fetch(`/api/v1/stats/processes/events.csv?days=${days}`)
      if (!res.ok) throw new ApiError(res.status, await readProblem(res))
      const filename = /filename="([^"]+)"/.exec(res.headers.get('content-disposition') ?? '')?.[1] ?? 'process-events.csv'
      const url = URL.createObjectURL(await res.blob())
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      a.click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (err) {
      setError(`CSV export failed: ${err?.message || 'Unknown error'}`)
    } finally {
      setDownloading(false)
    }
  }

  const t = stats?.totals
  const failureRate = t && t.runs ? Math.round((t.failed + t.killed) * 100 / t.runs) : 0

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Segmented value={days} onChange={setDays} options={RANGES.map((r) => ({ label: r.label, value: r.days }))} />
        <div className="flex items-center gap-2">
          {stats?.first_day && (
            <span className="whitespace-nowrap text-sm text-muted-foreground">Logged since {fmtDay(stats.first_day, true)}</span>
          )}
          <Button size="sm" variant="outline" onClick={downloadCsv} disabled={downloading} title="All events of this range as CSV">
            <DownloadIcon /> CSV
          </Button>
          <Button size="sm" variant="ghost" onClick={() => fetchStats(true)} disabled={loading} title="Recalculate from the event log">
            <RefreshCwIcon className={loading ? 'animate-spin' : ''} /> Refresh
          </Button>
        </div>
      </div>

      {error && <div className="rounded-lg border border-destructive/50 p-4 text-sm text-destructive">{error}</div>}

      {!stats && loading && (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
          {[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-24 rounded-xl" />)}
          <Skeleton className="h-72 rounded-xl sm:col-span-2 xl:col-span-5" />
        </div>
      )}

      {stats && t && (
        <div className={cn('flex flex-col gap-4 transition-opacity', loading && 'opacity-60')}>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
            <Kpi icon={ActivityIcon} label="Finished runs" value={full.format(t.runs)}
                 hint={`${full.format(t.completed)} completed`} />
            <Kpi icon={AlertTriangleIcon} label="Failed or killed" value={`${failureRate}%`}
                 hint={t.runs ? `${full.format(t.failed)} failed · ${full.format(t.killed)} killed` : 'No runs yet'} />
            <Kpi icon={RotateCwIcon} label="Service restarts" value={full.format(t.restarts)}
                 hint={t.gave_up || t.spawn_errors
                   ? <span className="text-destructive">{[t.gave_up && `${t.gave_up} gave up`, t.spawn_errors && `${t.spawn_errors} spawn errors`].filter(Boolean).join(' · ')}</span>
                   : 'After a service exited'} />
            <Kpi icon={TimerOffIcon} label="Timeouts / skipped" value={`${full.format(t.timeouts)} / ${full.format(t.skipped)}`}
                 hint="Scheduled runs over their timeout / overlapping" />
            <Kpi icon={t.actions ? HandIcon : ClockIcon} label={t.actions ? 'Control actions' : 'Avg run time'}
                 value={t.actions ? full.format(t.actions) : fmtDuration(t.avg_duration_ms)}
                 hint={t.actions ? `Avg run time ${fmtDuration(t.avg_duration_ms)}` : 'Over finished runs'} />
          </div>

          <DailyRunsChart stats={stats} />
          <ByNameTable stats={stats} />
        </div>
      )}

      <EventLog />
    </div>
  )
}

export default ProcessStatsView
