import { WidgetRendererProps } from '@/components/xchat/chat.types.ts'

type FunnelStep = { label: string; value: number }

type FunnelData = { title?: string; unit?: string; steps: FunnelStep[] }

const format = (n: number) => (Number.isInteger(n) ? n.toLocaleString() : n.toLocaleString(undefined, { maximumFractionDigits: 1 }))

const percent = (part: number, whole: number) => (whole > 0 ? `${+(part / whole * 100).toFixed(1)}%` : '–')

/**
 * geenii.funnel — data: { title?, unit?, steps: { label, value }[] }
 * Centred bars, each as wide as its share of the first step, with the share kept
 * overall and the drop-off from the previous step.
 */
export const FunnelWidget = ({ data }: WidgetRendererProps<FunnelData | null>) => {
  const steps = (Array.isArray(data?.steps) ? data.steps : [])
    .filter((s): s is FunnelStep => typeof s?.label === 'string' && Number.isFinite(s.value) && s.value >= 0)
  if (steps.length === 0) return <div className={'text-sm text-muted-foreground'}>No data</div>

  const top = Math.max(...steps.map((s) => s.value))
  const unit = data?.unit ? ` ${data.unit}` : ''

  return (
    <div className={'max-w-lg rounded-md border p-3'}>
      {data?.title && <div className={'mb-2 font-medium'}>{data.title}</div>}
      <ol className={'space-y-1'}>
        {steps.map((step, i) => {
          const previous = i > 0 ? steps[i - 1].value : null
          return (
            <li key={i}>
              {previous != null && (
                <div className={'py-0.5 text-center text-[11px] tabular-nums text-muted-foreground'}>
                  ↓ {percent(step.value, previous)} kept
                  {previous > step.value && ` · −${format(previous - step.value)}${unit}`}
                </div>
              )}
              <div className={'flex items-center gap-3 text-sm'}>
                <span className={'w-28 shrink-0 truncate'} title={step.label}>{step.label}</span>
                <div className={'flex min-w-0 flex-1 justify-center'}>
                  {/* at least a sliver, so a step with 0 is still visible */}
                  <div className={'h-6 rounded-sm'} title={`${step.label}: ${format(step.value)}${unit}`}
                       style={{
                         width: `${Math.max(1, top > 0 ? step.value / top * 100 : 0)}%`,
                         background: `color-mix(in oklch, var(--chart-1) ${100 - i / Math.max(1, steps.length - 1) * 50}%, var(--muted))`,
                       }} />
                </div>
                <span className={'w-24 shrink-0 text-right tabular-nums'}>
                  {format(step.value)}{unit}
                  <span className={'ml-1 text-xs text-muted-foreground'}>{percent(step.value, steps[0].value)}</span>
                </span>
              </div>
            </li>
          )
        })}
      </ol>
    </div>
  )
}
