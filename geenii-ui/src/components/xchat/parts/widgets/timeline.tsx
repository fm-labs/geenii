import { SystemMessageLevel, WidgetRendererProps } from '@/components/xchat/chat.types.ts'

type TimelineItem = { time: string; title: string; description?: string | null; level?: SystemMessageLevel }

const DOT_CLASSES: Record<SystemMessageLevel, string> = {
  info: 'bg-primary',
  warning: 'bg-amber-500',
  error: 'bg-destructive',
}

const formatTime = (time: string) => {
  const date = new Date(time)
  return isNaN(date.getTime()) ? time : date.toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })
}

/** geenii.timeline — data: { title?, items: { time: ISO datetime, title, description?, level? = info }[] } */
export const TimelineWidget = ({ data }: WidgetRendererProps<{ title?: string; items: TimelineItem[] } | null>) => {
  const items = Array.isArray(data?.items) ? data.items : []
  return (
    <div className={'rounded-md border p-3 max-w-lg'}>
      {data?.title && <div className={'font-medium mb-2'}>{data.title}</div>}
      <ol className={'relative ml-1 border-l pl-4 space-y-3 text-sm'}>
        {items.map((item, i) => (
          <li key={i} className={'relative'}>
            <span className={`absolute -left-[21px] top-1.5 size-2.5 rounded-full ring-2 ring-background ${DOT_CLASSES[item.level ?? 'info'] ?? DOT_CLASSES.info}`} />
            <time dateTime={item.time} className={'block text-xs text-muted-foreground tabular-nums'}>{formatTime(item.time)}</time>
            <div className={'font-medium'}>{item.title}</div>
            {item.description && <div className={'text-muted-foreground'}>{item.description}</div>}
          </li>
        ))}
      </ol>
    </div>
  )
}
