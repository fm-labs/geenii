import { WidgetRendererProps } from '@/components/xchat/chat.types.ts'

type StatItem = { label: string; value: string | number; unit?: string; delta?: number | null }

/** geenii.stat — data: { items: { label, value, unit?, delta? }[] }; delta is a percentage change */
export const StatWidget = ({ data }: WidgetRendererProps<{ items: StatItem[] } | null>) => {
  const items = Array.isArray(data?.items) ? data.items : []
  return (
    <div className={'flex flex-wrap gap-2'}>
      {items.map((item, i) => (
        <div key={i} className={'rounded-md border px-4 py-2 min-w-32'}>
          <div className={'text-xs text-muted-foreground'}>{item.label}</div>
          <div className={'text-2xl font-semibold tabular-nums'}>
            {item.value}{item.unit && <span className={'text-base font-normal text-muted-foreground'}> {item.unit}</span>}
          </div>
          {item.delta != null && (
            <div className={`text-xs tabular-nums ${item.delta < 0 ? 'text-destructive' : 'text-green-600'}`}>
              {item.delta < 0 ? '▼' : '▲'} {Math.abs(item.delta)}%
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
