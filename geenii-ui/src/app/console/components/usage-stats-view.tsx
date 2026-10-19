import * as React from 'react'
import {
  ActivityIcon, AlertTriangleIcon, CalendarDaysIcon, ClockIcon, CoinsIcon, DatabaseZapIcon, RefreshCwIcon,
} from 'lucide-react'
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { Button } from '@/components/ui/button.tsx'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.tsx'
import { Skeleton } from '@/components/ui/skeleton.tsx'
import { useApi } from '@/context/api-context.tsx'
import { cn } from 'cn'

/** Counters of GET /api/v1/stats/usage, for the whole range, a day or a breakdown row */
type UsageTotals = {
  calls: number
  failed: number
  input_tokens: number
  output_tokens: number
  total_tokens: number
  cache_read_input_tokens: number
  cache_creation_input_tokens: number
  duration_ms: number
  timed_calls: number
  avg_duration_ms: number | null
}

type UsageDay = UsageTotals & { date: string, tokens_by_provider: Record<string, number> }
type UsageRow = UsageTotals & { key: string }

type UsageStats = {
  start: string
  end: string
  first_day: string | null
  last_day: string | null
  totals: UsageTotals
  active_days: number
  daily: UsageDay[]
  hourly: number[]
  by_provider: UsageRow[]
  by_model: UsageRow[]
  by_source: UsageRow[]
  by_task: UsageRow[]
}

const RANGES = [
  { label: '7 days', days: 7 },
  { label: '30 days', days: 30 },
  { label: '90 days', days: 90 },
  { label: 'All time', days: 0 },
] as const

const COLORS = ['var(--chart-1)', 'var(--chart-2)', 'var(--chart-3)', 'var(--chart-4)', 'var(--chart-5)']
const color = (i: number) => COLORS[i % COLORS.length]
const OTHER_COLOR = 'var(--muted-foreground)'

const compact = new Intl.NumberFormat(undefined, { notation: 'compact', maximumFractionDigits: 1 })
const full = new Intl.NumberFormat()
const fmt = (n: number) => compact.format(n)
const fmtDuration = (ms: number | null) => ms === null ? '—' : ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`
const fmtDay = (iso: string, long = false) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, long ? { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' } : { day: 'numeric', month: 'short' })

/** The top `n` rows plus one "other" row summing the rest */
const topRows = (rows: UsageRow[], n: number): UsageRow[] => {
  if (rows.length <= n) return rows
  const rest = rows.slice(n)
  const other = rest.reduce((acc, r) => {
    for (const k of Object.keys(acc) as (keyof UsageTotals)[]) {
      if (k !== 'avg_duration_ms') (acc[k] as number) += r[k] as number
    }
    return acc
  }, { key: `${rest.length} other`, calls: 0, failed: 0, input_tokens: 0, output_tokens: 0, total_tokens: 0, cache_read_input_tokens: 0, cache_creation_input_tokens: 0, duration_ms: 0, timed_calls: 0, avg_duration_ms: null } as UsageRow)
  return [...rows.slice(0, n), other]
}

const ChartTooltip = ({ active, payload, label, labelFormatter }: {
  active?: boolean
  payload?: { name: string, value: number, color?: string, payload?: any }[]
  label?: string | number
  labelFormatter?: (label: any) => string
}) => {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-md border bg-popover px-3 py-2 text-xs text-popover-foreground shadow-md">
      {label !== undefined && <div className="mb-1 font-medium">{labelFormatter ? labelFormatter(label) : label}</div>}
      {payload.map((p) => (
        <div key={p.name} className="flex items-center gap-2">
          <span className="size-2 shrink-0 rounded-sm" style={{ background: p.color || p.payload?.fill }} />
          <span className="text-muted-foreground">{p.name}</span>
          <span className="ml-auto pl-3 font-mono tabular-nums">{full.format(p.value)}</span>
        </div>
      ))}
    </div>
  )
}

const axisProps = {
  stroke: 'var(--muted-foreground)',
  fontSize: 11,
  tickLine: false,
  axisLine: false,
} as const

const Kpi = ({ icon: Icon, label, value, hint }: { icon: React.ElementType, label: string, value: React.ReactNode, hint?: React.ReactNode }) => (
  <Card className="gap-1 py-4">
    <CardHeader className="px-4">
      <CardDescription className="flex items-center gap-1.5"><Icon size={14} /> {label}</CardDescription>
    </CardHeader>
    <CardContent className="px-4">
      <div className="text-2xl font-semibold tabular-nums">{value}</div>
      {hint && <div className="mt-0.5 text-xs text-muted-foreground">{hint}</div>}
    </CardContent>
  </Card>
)

const ChartCard = ({ title, description, actions, className, children }: {
  title: string
  description?: string
  actions?: React.ReactNode
  className?: string
  children: React.ReactNode
}) => (
  <Card className={cn('gap-3', className)}>
    <CardHeader>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <CardTitle className="text-base">{title}</CardTitle>
          {description && <CardDescription>{description}</CardDescription>}
        </div>
        {actions}
      </div>
    </CardHeader>
    <CardContent>{children}</CardContent>
  </Card>
)

const Segmented = <T extends string | number>({ options, value, onChange }: {
  options: readonly { label: string, value: NoInfer<T> }[]
  value: T
  onChange: (value: NoInfer<T>) => void
}) => (
  <div className="flex items-center rounded-md border p-0.5">
    {options.map((o) => (
      <Button key={String(o.value)} size="sm" variant={value === o.value ? 'secondary' : 'ghost'} className="h-7"
              onClick={() => onChange(o.value)} aria-pressed={value === o.value}>
        {o.label}
      </Button>
    ))}
  </div>
)

type DailyMetric = 'provider' | 'direction' | 'calls'

const DailyChart = ({ stats }: { stats: UsageStats }) => {
  const [metric, setMetric] = React.useState<DailyMetric>('provider')
  const providers = stats.by_provider.map((p) => p.key)
  const data = stats.daily.map((d) => ({ ...d, ...d.tokens_by_provider, succeeded: d.calls - d.failed }))
  const series = metric === 'provider'
    ? providers.map((p, i) => ({ key: p, name: p, color: color(i) }))
    : metric === 'direction'
      ? [{ key: 'input_tokens', name: 'Input', color: color(1) }, { key: 'output_tokens', name: 'Output', color: color(0) }]
      : [{ key: 'succeeded', name: 'Succeeded', color: color(1) }, { key: 'failed', name: 'Failed', color: 'var(--destructive)' }]
  // bars read better than areas for a few days
  const asBars = data.length <= 31

  const chartChildren = [
    <CartesianGrid key="grid" vertical={false} stroke="var(--border)" />,
    <XAxis key="x" dataKey="date" {...axisProps} tickFormatter={(d) => fmtDay(d)} minTickGap={24} />,
    <YAxis key="y" {...axisProps} tickFormatter={fmt} width={44} allowDecimals={false} />,
    <Tooltip key="tip" content={<ChartTooltip labelFormatter={(d) => fmtDay(d, true)} />} cursor={{ fill: 'var(--muted)', opacity: 0.5 }} />,
    <Legend key="legend" iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12 }} />,
  ]

  return (
    <ChartCard title={metric === 'calls' ? 'Calls per day' : 'Tokens per day'}
               description={`${fmtDay(stats.start)} – ${fmtDay(stats.end)}`}
               actions={<Segmented value={metric} onChange={setMetric} options={[
                 { label: 'By provider', value: 'provider' }, { label: 'Input / output', value: 'direction' }, { label: 'Calls', value: 'calls' },
               ]} />}>
      <ResponsiveContainer width="100%" height={280}>
        {asBars ? (
          <BarChart data={data} margin={{ left: 0, right: 8, top: 8 }}>
            {chartChildren}
            {series.map((s, i) => (
              <Bar key={s.key} dataKey={s.key} name={s.name} stackId="a" fill={s.color}
                   radius={i === series.length - 1 ? [3, 3, 0, 0] : 0} maxBarSize={36} />
            ))}
          </BarChart>
        ) : (
          <AreaChart data={data} margin={{ left: 0, right: 8, top: 8 }}>
            {chartChildren}
            {series.map((s) => (
              <Area key={s.key} dataKey={s.key} name={s.name} stackId="a" type="monotone"
                    stroke={s.color} fill={s.color} fillOpacity={0.35} strokeWidth={1.5} />
            ))}
          </AreaChart>
        )}
      </ResponsiveContainer>
    </ChartCard>
  )
}

const ProviderDonut = ({ stats }: { stats: UsageStats }) => {
  const rows = topRows(stats.by_provider, 4).filter((r) => r.total_tokens > 0)
  const total = stats.totals.total_tokens
  return (
    <ChartCard title="Tokens by provider" description={`${full.format(total)} tokens`}>
      {rows.length === 0 ? <NoData /> : (
        <div className="flex flex-col items-center gap-3">
          <div className="relative h-48 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={rows} dataKey="total_tokens" nameKey="key" innerRadius="62%" outerRadius="92%"
                     paddingAngle={rows.length > 1 ? 2 : 0} stroke="none">
                  {rows.map((r, i) => <Cell key={r.key} fill={i < 4 ? color(i) : OTHER_COLOR} />)}
                </Pie>
                <Tooltip content={<ChartTooltip />} />
              </PieChart>
            </ResponsiveContainer>
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-xl font-semibold tabular-nums">{fmt(total)}</span>
              <span className="text-xs text-muted-foreground">tokens</span>
            </div>
          </div>
          <ul className="w-full space-y-1 text-sm">
            {rows.map((r, i) => (
              <li key={r.key} className="flex items-center gap-2">
                <span className="size-2.5 shrink-0 rounded-sm" style={{ background: i < 4 ? color(i) : OTHER_COLOR }} />
                <span className="truncate">{r.key}</span>
                <span className="ml-auto font-mono text-xs tabular-nums text-muted-foreground">
                  {total ? Math.round(r.total_tokens * 100 / total) : 0}%
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </ChartCard>
  )
}

const TopModelsChart = ({ stats }: { stats: UsageStats }) => {
  const rows = stats.by_model.slice(0, 8).map((r) => ({ ...r, input: r.input_tokens, output: r.output_tokens }))
  return (
    <ChartCard title="Top models" description="Input and output tokens">
      {rows.length === 0 ? <NoData /> : (
        <ResponsiveContainer width="100%" height={Math.max(120, rows.length * 34 + 40)}>
          <BarChart data={rows} layout="vertical" margin={{ left: 0, right: 12 }}>
            <CartesianGrid horizontal={false} stroke="var(--border)" />
            <XAxis type="number" {...axisProps} tickFormatter={fmt} />
            <YAxis type="category" dataKey="key" {...axisProps} width={160}
                   tickFormatter={(k: string) => k.length > 24 ? `${k.slice(0, 23)}…` : k} />
            <Tooltip content={<ChartTooltip />} cursor={{ fill: 'var(--muted)', opacity: 0.5 }} />
            <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12 }} />
            <Bar dataKey="input" name="Input" stackId="a" fill={color(1)} maxBarSize={20} />
            <Bar dataKey="output" name="Output" stackId="a" fill={color(0)} radius={[0, 3, 3, 0]} maxBarSize={20} />
          </BarChart>
        </ResponsiveContainer>
      )}
    </ChartCard>
  )
}

const HourlyChart = ({ stats }: { stats: UsageStats }) => {
  const data = stats.hourly.map((calls, hour) => ({ hour, calls }))
  const peak = Math.max(...stats.hourly)
  return (
    <ChartCard title="Activity by hour" description="Calls per hour of day (server time)">
      {peak === 0 ? <NoData /> : (
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={data} margin={{ left: 0, right: 8, top: 8 }}>
            <CartesianGrid vertical={false} stroke="var(--border)" />
            <XAxis dataKey="hour" {...axisProps} tickFormatter={(h) => `${h}h`} interval={2} />
            <YAxis {...axisProps} width={36} allowDecimals={false} tickFormatter={fmt} />
            <Tooltip content={<ChartTooltip labelFormatter={(h) => `${h}:00 – ${h}:59`} />} cursor={{ fill: 'var(--muted)', opacity: 0.5 }} />
            <Bar dataKey="calls" name="Calls" radius={[3, 3, 0, 0]}>
              {data.map((d) => <Cell key={d.hour} fill={color(2)} fillOpacity={0.35 + 0.65 * (d.calls / peak)} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </ChartCard>
  )
}

type BreakdownKey = 'by_model' | 'by_provider' | 'by_source' | 'by_task'

const BreakdownTable = ({ stats }: { stats: UsageStats }) => {
  const [dimension, setDimension] = React.useState<BreakdownKey>('by_model')
  const rows = stats[dimension]
  const max = Math.max(1, ...rows.map((r) => r.total_tokens))
  return (
    <ChartCard title="Breakdown"
               description={dimension === 'by_source' ? 'Untagged calls were logged before callers were recorded.' : undefined}
               actions={<Segmented value={dimension} onChange={setDimension} options={[
                 { label: 'Model', value: 'by_model' }, { label: 'Provider', value: 'by_provider' },
                 { label: 'Source', value: 'by_source' }, { label: 'Task', value: 'by_task' },
               ]} />}>
      {rows.length === 0 ? <NoData /> : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-xs text-muted-foreground">
                <th className="py-2 pr-3 font-medium">Name</th>
                <th className="px-3 py-2 text-right font-medium">Calls</th>
                <th className="px-3 py-2 text-right font-medium">Failed</th>
                <th className="px-3 py-2 text-right font-medium">Input</th>
                <th className="px-3 py-2 text-right font-medium">Output</th>
                <th className="px-3 py-2 text-right font-medium">Cache read</th>
                <th className="px-3 py-2 text-right font-medium">Avg time</th>
                <th className="w-1/5 py-2 pl-3 font-medium">Total tokens</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.key} className="border-b last:border-0 hover:bg-muted/40">
                  <td className="max-w-64 truncate py-1.5 pr-3 font-mono text-xs" title={r.key}>{r.key}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums">{full.format(r.calls)}</td>
                  <td className={cn('px-3 py-1.5 text-right tabular-nums', r.failed ? 'text-destructive' : 'text-muted-foreground')}>{r.failed}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums" title={full.format(r.input_tokens)}>{fmt(r.input_tokens)}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums" title={full.format(r.output_tokens)}>{fmt(r.output_tokens)}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums text-muted-foreground" title={full.format(r.cache_read_input_tokens)}>
                    {r.cache_read_input_tokens ? fmt(r.cache_read_input_tokens) : '—'}
                  </td>
                  <td className="px-3 py-1.5 text-right tabular-nums text-muted-foreground">{fmtDuration(r.avg_duration_ms)}</td>
                  <td className="py-1.5 pl-3">
                    <div className="flex items-center gap-2">
                      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
                        <div className="h-full rounded-full" style={{ width: `${r.total_tokens * 100 / max}%`, background: color(0) }} />
                      </div>
                      <span className="w-12 text-right font-mono text-xs tabular-nums" title={full.format(r.total_tokens)}>{fmt(r.total_tokens)}</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </ChartCard>
  )
}

const NoData = () => <p className="py-8 text-center text-sm text-muted-foreground">No usage in this range.</p>

export const UsageStatsView = () => {
  const { fetchJson } = useApi()
  const [days, setDays] = React.useState<number>(30)
  const [stats, setStats] = React.useState<UsageStats | null>(null)
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)

  const fetchStats = React.useCallback(async (refresh = false) => {
    setLoading(true)
    setError(null)
    try {
      setStats(await fetchJson(`/api/v1/stats/usage?days=${days}${refresh ? '&refresh=true' : ''}`))
    } catch (err) {
      console.error('Error fetching usage stats', err)
      setError(err?.message || 'Unknown error')
    } finally {
      setLoading(false)
    }
  }, [fetchJson, days])

  React.useEffect(() => {
    fetchStats()
  }, [fetchStats])

  const t = stats?.totals
  const cacheShare = t && t.input_tokens ? Math.round(t.cache_read_input_tokens * 100 / t.input_tokens) : 0

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Segmented value={days} onChange={setDays} options={RANGES.map((r) => ({ label: r.label, value: r.days }))} />
        <div className="flex items-center gap-2">
          {stats?.first_day && (
            <span className="text-sm text-muted-foreground whitespace-nowrap">Logged since {fmtDay(stats.first_day, true)}</span>
          )}
          <Button size="sm" variant="ghost" onClick={() => fetchStats(true)} disabled={loading} title="Recalculate from the usage log">
            <RefreshCwIcon className={loading ? 'animate-spin' : ''} /> Refresh
          </Button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/50 p-4 text-sm text-destructive">
          Failed to load usage stats: {error}
        </div>
      )}

      {!stats && loading && (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
          {[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-24 rounded-xl" />)}
          <Skeleton className="h-80 rounded-xl sm:col-span-2 xl:col-span-5" />
        </div>
      )}

      {stats && t && (
        <div className={cn('flex flex-col gap-4 transition-opacity', loading && 'opacity-60')}>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
            <Kpi icon={ActivityIcon} label="Calls" value={full.format(t.calls)}
                 hint={t.failed ? <span className="inline-flex items-center gap-1 text-destructive"><AlertTriangleIcon size={12} /> {t.failed} failed</span> : 'No failures'} />
            <Kpi icon={CoinsIcon} label="Total tokens" value={fmt(t.total_tokens)}
                 hint={`${fmt(t.input_tokens)} in · ${fmt(t.output_tokens)} out`} />
            <Kpi icon={DatabaseZapIcon} label="Prompt cache" value={`${cacheShare}%`}
                 hint={`${fmt(t.cache_read_input_tokens)} input tokens read from cache`} />
            <Kpi icon={ClockIcon} label="Avg response time" value={fmtDuration(t.avg_duration_ms)}
                 hint={t.timed_calls ? `over ${full.format(t.timed_calls)} local calls` : 'Only reported by local models'} />
            <Kpi icon={CalendarDaysIcon} label="Active days" value={`${stats.active_days} / ${stats.daily.length}`}
                 hint={stats.active_days ? `${fmt(Math.round(t.total_tokens / stats.active_days))} tokens per active day` : 'No usage yet'} />
          </div>

          <div className="grid gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
            <DailyChart stats={stats} />
            <ProviderDonut stats={stats} />
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <TopModelsChart stats={stats} />
            <HourlyChart stats={stats} />
          </div>

          <BreakdownTable stats={stats} />
        </div>
      )}
    </div>
  )
}

export default UsageStatsView
