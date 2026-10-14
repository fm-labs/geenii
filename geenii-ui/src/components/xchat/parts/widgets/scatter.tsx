import { WidgetRendererProps } from '@/components/xchat/chat.types.ts'

type Point = { x: number; y: number; label?: string; size?: number }

type Axis = { label?: string; unit?: string }

type ScatterData = { title?: string; x?: Axis; y?: Axis; series: { name: string; points: Point[] }[] }

const COLORS = ['var(--chart-1)', 'var(--chart-2)', 'var(--chart-3)', 'var(--chart-4)', 'var(--chart-5)']

// chart area inside the svg viewBox; the left margin holds the y labels, the bottom one the x labels
const W = 400, H = 220, LEFT = 40, BOTTOM = 30, TOP = 8, RIGHT = 10
const MIN_R = 3, MAX_R = 10

const label = (n: number) => (Math.abs(n) >= 1000 ? `${+(n / 1000).toFixed(1)}k` : String(+n.toFixed(2)))

/** [min, max] of the values, widened by 5% on each side so points don't sit on the frame */
const range = (values: number[]): [number, number] => {
  const [min, max] = [Math.min(...values), Math.max(...values)]
  const pad = (max - min) * 0.05 || Math.abs(min) * 0.1 || 1
  return [min - pad, max + pad]
}

/**
 * geenii.scatter — data: { title?, x?: { label?, unit? }, y?: { label?, unit? },
 *   series: { name, points: { x, y, label?, size? }[] }[] }
 * Points with a `size` become bubbles (area by size); points with a `label` show it next to the point.
 */
export const ScatterWidget = ({ data }: WidgetRendererProps<ScatterData | null>) => {
  const series = (Array.isArray(data?.series) ? data.series : [])
    .map((s) => ({ ...s, points: (Array.isArray(s?.points) ? s.points : [])
      .filter((p) => Number.isFinite(p?.x) && Number.isFinite(p?.y)) }))
  const points = series.flatMap((s) => s.points)
  if (points.length === 0) return <div className={'text-sm text-muted-foreground'}>No data</div>

  const [xMin, xMax] = range(points.map((p) => p.x))
  const [yMin, yMax] = range(points.map((p) => p.y))
  const sx = (x: number) => LEFT + (x - xMin) / (xMax - xMin) * (W - LEFT - RIGHT)
  const sy = (y: number) => TOP + (1 - (y - yMin) / (yMax - yMin)) * (H - TOP - BOTTOM)
  const maxSize = Math.max(0, ...points.map((p) => (typeof p.size === 'number' ? p.size : 0)))
  const radius = (p: Point) => (typeof p.size === 'number' && p.size > 0 && maxSize > 0
    ? MIN_R + Math.sqrt(p.size / maxSize) * (MAX_R - MIN_R) : MIN_R)
  const unit = (axis?: Axis) => (axis?.unit ? ` ${axis.unit}` : '')
  const axisName = (axis: Axis | undefined, fallback: string) => axis?.label ?? fallback

  return (
    <div className={'max-w-lg rounded-md border p-3'}>
      {data?.title && <div className={'mb-2 font-medium'}>{data.title}</div>}
      <svg viewBox={`0 0 ${W} ${H}`} className={'h-auto w-full text-muted-foreground'} role={'img'}
           aria-label={data?.title ?? 'Scatter chart'}>
        <rect x={LEFT} y={TOP} width={W - LEFT - RIGHT} height={H - TOP - BOTTOM}
              fill={'none'} stroke={'currentColor'} strokeOpacity={0.2} />
        <g fontSize={10} fill={'currentColor'}>
          <text x={LEFT - 4} y={TOP + 8} textAnchor={'end'}>{label(yMax)}</text>
          <text x={LEFT - 4} y={H - BOTTOM} textAnchor={'end'}>{label(yMin)}</text>
          <text x={LEFT} y={H - BOTTOM + 12} textAnchor={'start'}>{label(xMin)}</text>
          <text x={W - RIGHT} y={H - BOTTOM + 12} textAnchor={'end'}>{label(xMax)}</text>
          {data?.x?.label && <text x={(LEFT + W - RIGHT) / 2} y={H - 4} textAnchor={'middle'}>{data.x.label}{unit(data.x)}</text>}
          {data?.y?.label && (
            <text x={0} y={0} textAnchor={'middle'}
                  transform={`translate(10 ${(TOP + H - BOTTOM) / 2}) rotate(-90)`}>{data.y.label}{unit(data.y)}</text>
          )}
        </g>
        {series.map((s, i) => {
          const color = COLORS[i % COLORS.length]
          return (
            <g key={i}>
              {s.points.map((p, j) => (
                <g key={j}>
                  <circle cx={sx(p.x)} cy={sy(p.y)} r={radius(p)} fill={color} fillOpacity={0.7} stroke={color}>
                    <title>
                      {`${p.label ? `${p.label} · ` : ''}${s.name}: ${axisName(data?.x, 'x')} ${p.x}${unit(data?.x)}, ` +
                        `${axisName(data?.y, 'y')} ${p.y}${unit(data?.y)}${p.size != null ? `, size ${p.size}` : ''}`}
                    </title>
                  </circle>
                  {p.label && (
                    <text x={sx(p.x) + radius(p) + 2} y={sy(p.y) + 3} fontSize={9} fill={'currentColor'}>{p.label}</text>
                  )}
                </g>
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
