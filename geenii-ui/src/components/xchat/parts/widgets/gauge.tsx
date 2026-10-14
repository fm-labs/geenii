import { WidgetRendererProps } from '@/components/xchat/chat.types.ts'

type GaugeData = {
  value: number
  min?: number
  max?: number
  label?: string
  unit?: string
  /** values from which the gauge turns amber / red */
  thresholds?: { warning?: number; error?: number }
}

// a half circle from the left (180°) to the right (0°), as one path so its length can be normalized
const ARC = 'M 10 60 A 50 50 0 0 1 110 60'

/**
 * geenii.gauge — data: { value, min? = 0, max? = 100, label?, unit?, thresholds?: { warning?, error? } }
 * A half-circle meter; past `thresholds.warning` it turns amber, past `thresholds.error` red.
 */
export const GaugeWidget = ({ data }: WidgetRendererProps<GaugeData | null>) => {
  if (typeof data?.value !== 'number') return <div className={'text-sm text-muted-foreground'}>No value</div>
  const min = data.min ?? 0
  const max = data.max ?? 100
  const fraction = max > min ? Math.min(1, Math.max(0, (data.value - min) / (max - min))) : 0
  const { warning, error } = data.thresholds ?? {}
  const color = error != null && data.value >= error ? 'var(--destructive)'
    : warning != null && data.value >= warning ? 'rgb(245 158 11)' // amber-500
      : 'var(--chart-2)'
  const value = Number.isInteger(data.value) ? data.value : +data.value.toFixed(1)

  return (
    <div className={'inline-flex flex-col items-center rounded-md border px-4 pt-3 pb-2'}>
      <svg viewBox={'0 0 120 68'} className={'w-40'} role={'img'}
           aria-label={`${data.label ?? 'Value'}: ${value}${data.unit ?? ''} of ${max}`}>
        <path d={ARC} pathLength={100} fill={'none'} stroke={'var(--muted)'} strokeWidth={10} strokeLinecap={'round'} />
        {fraction > 0 && (
          <path d={ARC} pathLength={100} fill={'none'} stroke={color} strokeWidth={10} strokeLinecap={'round'}
                strokeDasharray={`${fraction * 100} 100`} />
        )}
        <text x={60} y={56} textAnchor={'middle'} fontSize={18} fontWeight={600} fill={'currentColor'}>
          {value}<tspan fontSize={10} fontWeight={400}>{data.unit ?? ''}</tspan>
        </text>
        <g fontSize={7} fill={'currentColor'} opacity={0.6}>
          <text x={10} y={68} textAnchor={'middle'}>{min}</text>
          <text x={110} y={68} textAnchor={'middle'}>{max}</text>
        </g>
      </svg>
      {data.label && <div className={'text-xs text-muted-foreground'}>{data.label}</div>}
    </div>
  )
}
