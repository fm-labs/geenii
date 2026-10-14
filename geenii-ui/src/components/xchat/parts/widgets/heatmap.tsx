import { WidgetRendererProps } from '@/components/xchat/chat.types.ts'

type HeatmapData = { title?: string; unit?: string; weeks?: number; days: { date: string; value: number }[] }

const DAY_MS = 86_400_000
const MAX_WEEKS = 53
const LEVELS = [0, 25, 50, 75, 100] // color strength per level, in %

const isoDate = (day: number) => new Date(day * DAY_MS).toISOString().slice(0, 10)

/** "YYYY-MM-DD…" as a UTC day number (days since the epoch), or null for invalid dates such as 2026-13-01 */
const dayNumber = (date: string) => {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(date)
  if (!match) return null
  const day = Date.UTC(+match[1], +match[2] - 1, +match[3]) / DAY_MS
  // Date.UTC rolls invalid months/days over; only accept dates that survive the round trip
  return isoDate(day) === match[0] ? day : null
}

// Monday = 0 … Sunday = 6 (1970-01-01, day 0, was a Thursday)
const weekday = (day: number) => (day + 3) % 7

const mondayOf = (day: number) => day - weekday(day)

/** 0 for no activity, else 1–4 by the share of the highest value */
const level = (value: number, max: number) => (value <= 0 || max <= 0 ? 0 : Math.min(4, Math.ceil(value / max * 4)))

/**
 * geenii.heatmap — data: { title?, unit?, weeks?, days: { date: 'YYYY-MM-DD', value }[] }
 * A GitHub-style activity grid, one column per week (Monday on top), ending with the latest date.
 * `weeks` defaults to the span of the data (at most 53).
 */
export const HeatmapWidget = ({ data }: WidgetRendererProps<HeatmapData | null>) => {
  const values = new Map<number, number>()
  for (const d of Array.isArray(data?.days) ? data.days : []) {
    const day = typeof d?.date === 'string' ? dayNumber(d.date) : null
    if (day != null && typeof d.value === 'number') values.set(day, (values.get(day) ?? 0) + d.value)
  }
  if (values.size === 0) return <div className={'text-sm text-muted-foreground'}>No data</div>

  const days = [...values.keys()]
  const last = Math.max(...days)
  const span = (mondayOf(last) - mondayOf(Math.min(...days))) / 7 + 1
  const weeks = Math.min(MAX_WEEKS, Math.max(1, Math.round(data?.weeks ?? span)))
  const first = mondayOf(last) - (weeks - 1) * 7 // the Monday of the first column
  const max = Math.max(...values.values())
  const total = [...values.entries()].filter(([day]) => day >= first).reduce((sum, [, v]) => sum + v, 0)
  const unit = data?.unit ? ` ${data.unit}` : ''

  const columns = Array.from({ length: weeks }, (_, w) => Array.from({ length: 7 }, (_, d) => first + w * 7 + d))
  // month name above the first column that starts in a new month
  const monthOf = (day: number) => new Date(day * DAY_MS).getUTCMonth()
  const monthLabel = (w: number) => (w === 0 || monthOf(columns[w][0]) !== monthOf(columns[w - 1][0])
    ? new Date(columns[w][0] * DAY_MS).toLocaleDateString([], { month: 'short', timeZone: 'UTC' }) : '')

  return (
    <div className={'max-w-full rounded-md border p-3'}>
      {data?.title && <div className={'mb-2 text-sm font-medium'}>{data.title}</div>}
      <div className={'overflow-x-auto'}>
        <div className={'inline-flex gap-[3px]'}>
          {columns.map((column, w) => (
            <div key={w} className={'flex flex-col gap-[3px]'}>
              <div className={'h-3 w-3 overflow-visible whitespace-nowrap text-[9px] leading-3 text-muted-foreground'}>{monthLabel(w)}</div>
              {column.map((day) => {
                const value = values.get(day) ?? 0
                const lvl = level(value, max)
                return day > last ? <div key={day} className={'size-3'} /> : (
                  <div key={day} className={'size-3 rounded-[2px]'} title={`${isoDate(day)}: ${value}${unit}`}
                       style={{ background: lvl === 0 ? 'var(--muted)' : `color-mix(in oklch, var(--chart-2) ${LEVELS[lvl]}%, var(--muted))` }} />
                )
              })}
            </div>
          ))}
        </div>
      </div>
      <div className={'mt-2 flex items-center justify-between gap-4 text-xs text-muted-foreground'}>
        <span className={'tabular-nums'}>{total}{unit} in {weeks} {weeks === 1 ? 'week' : 'weeks'}</span>
        <span className={'flex items-center gap-1'}>
          Less
          {LEVELS.map((pct, i) => (
            <span key={i} className={'size-2.5 rounded-[2px]'}
                  style={{ background: i === 0 ? 'var(--muted)' : `color-mix(in oklch, var(--chart-2) ${pct}%, var(--muted))` }} />
          ))}
          More
        </span>
      </div>
    </div>
  )
}
