import { WidgetRendererProps } from '@/components/xchat/chat.types.ts'

type Point = { x: number | string; y: number }

type LineChartData = { title?: string; unit?: string; series: { name: string; points: Point[] }[] }

const COLORS = ['var(--chart-1)', 'var(--chart-2)', 'var(--chart-3)', 'var(--chart-4)', 'var(--chart-5)']

// chart area inside the svg viewBox; the left margin holds the y labels, the bottom one the x labels
const W = 400, H = 160, LEFT = 40, BOTTOM = 18, TOP = 6, RIGHT = 6

/** x as a number: numbers as-is, strings as dates (ISO) */
const xValue = (x: number | string) => (typeof x === 'number' ? x : Date.parse(x))

const xLabel = (x: number | string) => {
  if (typeof x === 'number') return String(x)
  const date = new Date(x)
  return isNaN(date.getTime()) ? x : date.toLocaleDateString()
}

const yLabel = (y: number) => (Math.abs(y) >= 1000 ? `${+(y / 1000).toFixed(1)}k` : String(+y.toFixed(2)))

/** geenii.linechart — data: { title?, unit?, series: { name, points: { x, y }[] }[] }; x is a number or an ISO date */
export const LineChartWidget = ({ data }: WidgetRendererProps<LineChartData | null>) => {
  const series = (Array.isArray(data?.series) ? data.series : [])
    .map((s) => ({ ...s, points: (s.points ?? []).filter((p) => !isNaN(xValue(p.x)) && typeof p.y === 'number') }))
  const points = series.flatMap((s) => s.points)
  if (points.length === 0) return <div className={'text-sm text-muted-foreground'}>No data</div>

  const xs = points.map((p) => xValue(p.x))
  const ys = points.map((p) => p.y)
  const [xMin, xMax] = [Math.min(...xs), Math.max(...xs)]
  const [yMin, yMax] = [Math.min(0, ...ys), Math.max(...ys)]
  const sx = (x: number) => LEFT + (xMax > xMin ? (x - xMin) / (xMax - xMin) : 0.5) * (W - LEFT - RIGHT)
  const sy = (y: number) => TOP + (yMax > yMin ? 1 - (y - yMin) / (yMax - yMin) : 0.5) * (H - TOP - BOTTOM)
  const first = points.find((p) => xValue(p.x) === xMin)!
  const last = points.find((p) => xValue(p.x) === xMax)!

  return (
    <div className={'rounded-md border p-3 max-w-lg'}>
      {data?.title && <div className={'font-medium mb-2'}>{data.title}</div>}
      <svg viewBox={`0 0 ${W} ${H}`} className={'w-full h-auto text-muted-foreground'} role={'img'}
           aria-label={data?.title ?? 'Line chart'}>
        <g fontSize={10} fill={'currentColor'}>
          <text x={LEFT - 4} y={sy(yMax) + 4} textAnchor={'end'}>{yLabel(yMax)}{data?.unit ? ` ${data.unit}` : ''}</text>
          <text x={LEFT - 4} y={sy(yMin)} textAnchor={'end'}>{yLabel(yMin)}</text>
          <text x={LEFT} y={H - 4} textAnchor={'start'}>{xLabel(first.x)}</text>
          {xMax > xMin && <text x={W - RIGHT} y={H - 4} textAnchor={'end'}>{xLabel(last.x)}</text>}
        </g>
        <line x1={LEFT} x2={W - RIGHT} y1={sy(yMin)} y2={sy(yMin)} stroke={'currentColor'} strokeOpacity={0.3} />
        <line x1={LEFT} x2={W - RIGHT} y1={sy(yMax)} y2={sy(yMax)} stroke={'currentColor'} strokeOpacity={0.1} />
        {series.map((s, i) => {
          const sorted = [...s.points].sort((a, b) => xValue(a.x) - xValue(b.x))
          const color = COLORS[i % COLORS.length]
          return (
            <g key={i}>
              <polyline fill={'none'} stroke={color} strokeWidth={2} strokeLinejoin={'round'}
                        points={sorted.map((p) => `${sx(xValue(p.x))},${sy(p.y)}`).join(' ')} />
              {sorted.map((p, j) => (
                <circle key={j} cx={sx(xValue(p.x))} cy={sy(p.y)} r={2.5} fill={color}>
                  <title>{`${s.name}: ${p.y}${data?.unit ? ` ${data.unit}` : ''} (${xLabel(p.x)})`}</title>
                </circle>
              ))}
            </g>
          )
        })}
      </svg>
      {series.length > 1 && (
        <div className={'mt-2 flex flex-wrap gap-3 text-xs text-muted-foreground'}>
          {series.map((s, i) => (
            <span key={i} className={'inline-flex items-center gap-1'}>
              <span className={'inline-block size-2 rounded-full'} style={{ background: COLORS[i % COLORS.length] }} />
              {s.name}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}
