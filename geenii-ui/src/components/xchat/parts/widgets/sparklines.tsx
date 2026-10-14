import { WidgetRendererProps } from '@/components/xchat/chat.types.ts'

type SparklineRow = { label: string; values: number[]; unit?: string; description?: string; good?: 'up' | 'down' }

type SparklinesData = { title?: string; unit?: string; rows: SparklineRow[] }

const W = 100, H = 24, PAD = 2

const format = (n: number) => (Math.abs(n) >= 10_000 ? `${+(n / 1000).toFixed(1)}k`
  : Number.isInteger(n) ? n.toLocaleString() : n.toLocaleString(undefined, { maximumFractionDigits: 2 }))

const Sparkline = ({ values, label }: { values: number[]; label: string }) => {
  const [min, max] = [Math.min(...values), Math.max(...values)]
  const x = (i: number) => PAD + (values.length > 1 ? i / (values.length - 1) : 0.5) * (W - 2 * PAD)
  const y = (v: number) => PAD + (max > min ? 1 - (v - min) / (max - min) : 0.5) * (H - 2 * PAD)
  const line = values.map((v, i) => `${x(i)},${y(v)}`).join(' ')
  const last = values.length - 1
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className={'h-6 w-24'} preserveAspectRatio={'none'} role={'img'}
         aria-label={`${label}: ${values.map(format).join(', ')}`}>
      <polygon points={`${x(0)},${H} ${line} ${x(last)},${H}`} fill={'var(--chart-1)'} fillOpacity={0.15} />
      <polyline points={line} fill={'none'} stroke={'var(--chart-1)'} strokeWidth={1.5}
                strokeLinejoin={'round'} vectorEffect={'non-scaling-stroke'} />
      <circle cx={x(last)} cy={y(values[last])} r={2} fill={'var(--chart-1)'} />
    </svg>
  )
}

/**
 * geenii.sparklines — data: { title?, unit?, rows: { label, values: number[], unit?, description?, good? = 'up' }[] }
 * A table with a small trend chart per row, the latest value and the change from first to last.
 * `good: 'down'` marks rows where falling is good (latency, errors), so the change is coloured the other way.
 */
export const SparklinesWidget = ({ data }: WidgetRendererProps<SparklinesData | null>) => {
  const rows = (Array.isArray(data?.rows) ? data.rows : [])
    .filter((r): r is SparklineRow => typeof r?.label === 'string' && Array.isArray(r.values))
    .map((r) => ({ ...r, values: r.values.filter((v) => Number.isFinite(v)) }))
    .filter((r) => r.values.length > 0)
  if (rows.length === 0) return <div className={'text-sm text-muted-foreground'}>No data</div>

  return (
    <div className={'max-w-lg rounded-md border p-3'}>
      {data?.title && <div className={'mb-2 font-medium'}>{data.title}</div>}
      <table className={'w-full text-sm'}>
        <tbody>
          {rows.map((row, i) => {
            const first = row.values[0]
            const last = row.values[row.values.length - 1]
            const change = first !== 0 && row.values.length > 1 ? (last - first) / Math.abs(first) * 100 : null
            const better = change == null || change === 0 ? null : (change > 0) === ((row.good ?? 'up') === 'up')
            const unit = row.unit ?? data?.unit
            return (
              <tr key={i} className={'border-b last:border-0'}>
                <td className={'max-w-40 py-1.5 pr-3 align-middle'}>
                  <div className={'truncate'}>{row.label}</div>
                  {row.description && <div className={'truncate text-xs text-muted-foreground'}>{row.description}</div>}
                </td>
                <td className={'py-1.5 pr-3 align-middle'}><Sparkline values={row.values} label={row.label} /></td>
                <td className={'whitespace-nowrap py-1.5 pr-3 text-right align-middle tabular-nums'}>
                  {format(last)}{unit && <span className={'text-xs text-muted-foreground'}> {unit}</span>}
                </td>
                <td className={`whitespace-nowrap py-1.5 text-right align-middle text-xs tabular-nums ${
                  better == null ? 'text-muted-foreground' : better ? 'text-green-600' : 'text-destructive'}`}>
                  {change == null ? '' : change === 0 ? '±0%' : `${change > 0 ? '▲' : '▼'} ${+Math.abs(change).toFixed(1)}%`}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
