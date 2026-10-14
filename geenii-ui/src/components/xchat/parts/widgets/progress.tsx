import { WidgetRendererProps } from '@/components/xchat/chat.types.ts'

type ProgressData = { label?: string; value?: number | null; max?: number; status?: 'running' | 'done' | 'error' }

/** geenii.progress — data: { label?, value?, max? = 100, status? }; without a value the bar is indeterminate */
export const ProgressWidget = ({ data }: WidgetRendererProps<ProgressData | null>) => {
  const max = data?.max || 100
  const status = data?.status ?? 'running'
  const percent = data?.value == null ? null : Math.min(100, Math.max(0, data.value / max * 100))
  const barClass = status === 'error' ? 'bg-destructive' : status === 'done' ? 'bg-green-600' : 'bg-primary'
  return (
    <div className={'max-w-md space-y-1'}>
      <div className={'flex justify-between gap-2 text-sm'}>
        <span className={'truncate'}>{data?.label}</span>
        <span className={'tabular-nums text-muted-foreground'}>
          {status === 'error' ? 'failed' : percent == null ? status : `${Math.round(percent)}%`}
        </span>
      </div>
      <div className={'h-2 rounded-full bg-muted overflow-hidden'}>
        <div className={`h-full rounded-full ${barClass} ${percent == null && status === 'running' ? 'animate-pulse' : ''}`}
             style={{ width: `${percent ?? 100}%` }} />
      </div>
    </div>
  )
}
