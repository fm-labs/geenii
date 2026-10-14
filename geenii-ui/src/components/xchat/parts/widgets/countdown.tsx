import { WidgetRendererProps } from '@/components/xchat/chat.types.ts'
import { useNow } from './use-now.ts'

const formatDuration = (ms: number) => {
  const total = Math.floor(ms / 1000)
  const days = Math.floor(total / 86400)
  const time = [Math.floor(total / 3600) % 24, Math.floor(total / 60) % 60, total % 60]
    .map((n) => String(n).padStart(2, '0')).join(':')
  return days > 0 ? `${days}d ${time}` : time
}

/** geenii.countdown — data: { until: ISO datetime, label? } */
export const CountdownWidget = ({ data }: WidgetRendererProps<{ until: string; label?: string } | null>) => {
  const until = data?.until ? new Date(data.until).getTime() : NaN
  const now = useNow(!isNaN(until) && until > Date.now())
  const left = until - now.getTime()
  return (
    <div className={'inline-flex flex-col rounded-md border px-4 py-2'}>
      <span className={'text-2xl font-semibold tabular-nums'}>
        {isNaN(until) ? 'Invalid date' : left > 0 ? formatDuration(left) : 'Done'}
      </span>
      {data?.label && <span className={'text-xs text-muted-foreground'}>{data.label}</span>}
    </div>
  )
}
