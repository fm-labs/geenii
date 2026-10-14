import { WidgetRendererProps } from '@/components/xchat/chat.types.ts'
import { useNow } from './use-now.ts'

/** geenii.clock — data: { timezone?: string, label?: string } */
export const ClockWidget = ({ data }: WidgetRendererProps<{ timezone?: string; label?: string } | null>) => {
  const now = useNow()

  let time: string
  try {
    time = now.toLocaleTimeString(undefined, { timeZone: data?.timezone })
  } catch {
    time = now.toLocaleTimeString()  // unknown timezone
  }
  return (
    <div className={'inline-flex flex-col rounded-md border px-4 py-2'}>
      <span className={'text-2xl font-semibold tabular-nums'}>{time}</span>
      {(data?.label || data?.timezone) && (
        <span className={'text-xs text-muted-foreground'}>{data?.label || data?.timezone}</span>
      )}
    </div>
  )
}
