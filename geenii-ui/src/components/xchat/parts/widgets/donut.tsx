import { WidgetRendererProps } from '@/components/xchat/chat.types.ts'

type DonutItem = { label: string; value: number; color?: string }

type DonutData = { title?: string; unit?: string; items: DonutItem[]; hole?: boolean }

const COLORS = ['var(--chart-1)', 'var(--chart-2)', 'var(--chart-3)', 'var(--chart-4)', 'var(--chart-5)']

const format = (n: number) => (Number.isInteger(n) ? String(n) : n.toFixed(1))

/**
 * geenii.donut — data: { title?, unit?, items: { label, value, color? }[], hole? = true }
 * A donut (or with `hole: false`, a pie) chart with a legend; items with a value ≤ 0 are left out.
 */
export const DonutWidget = ({ data }: WidgetRendererProps<DonutData | null>) => {
  const items = (Array.isArray(data?.items) ? data.items : [])
    .filter((i): i is DonutItem => typeof i?.value === 'number' && i.value > 0)
  const total = items.reduce((sum, i) => sum + i.value, 0)
  if (total === 0) return <div className={'text-sm text-muted-foreground'}>No data</div>

  const colorOf = (item: DonutItem, i: number) => item.color || COLORS[i % COLORS.length]
  // conic-gradient stops: each item is a slice from the running total to the next
  let start = 0
  const stops = items.map((item, i) => {
    const end = start + item.value / total * 100
    const stop = `${colorOf(item, i)} ${start}% ${end}%`
    start = end
    return stop
  })
  const unit = data?.unit ? ` ${data.unit}` : ''
  const hole = data?.hole ?? true

  return (
    <div className={'inline-flex max-w-lg flex-wrap items-center gap-4 rounded-md border p-3'}>
      <div className={'relative size-28 shrink-0 rounded-full'} style={{ background: `conic-gradient(${stops.join(', ')})` }}
           role={'img'} aria-label={items.map((i) => `${i.label}: ${format(i.value)}${unit}`).join(', ')}>
        {hole && (
          <div className={'absolute inset-[22%] flex flex-col items-center justify-center rounded-full bg-background text-center'}>
            <span className={'text-sm font-semibold tabular-nums leading-tight'}>{format(total)}</span>
            {data?.unit && <span className={'text-[10px] text-muted-foreground leading-tight'}>{data.unit}</span>}
          </div>
        )}
      </div>
      <div className={'min-w-0 text-sm'}>
        {data?.title && <div className={'mb-1 font-medium'}>{data.title}</div>}
        <ul className={'space-y-0.5'}>
          {items.map((item, i) => (
            <li key={i} className={'flex items-center gap-2'}>
              <span className={'size-2.5 shrink-0 rounded-sm'} style={{ background: colorOf(item, i) }} />
              <span className={'truncate'}>{item.label}</span>
              <span className={'ml-auto pl-2 tabular-nums text-muted-foreground'}>
                {format(item.value)}{unit} · {Math.round(item.value / total * 100)}%
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
