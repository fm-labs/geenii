import React from 'react'
import { WidgetRendererProps } from '@/components/xchat/chat.types.ts'

type BarChartData = { title?: string; unit?: string; max?: number; items: { label: string; value: number }[] }

/** geenii.barchart — data: { title?, unit?, max?, items: { label, value }[] }; max defaults to the largest value */
export const BarChartWidget = ({ data }: WidgetRendererProps<BarChartData | null>) => {
  const items = Array.isArray(data?.items) ? data.items : []
  const max = data?.max ?? Math.max(0, ...items.map((item) => item.value))
  return (
    <div className={'rounded-md border p-3 max-w-lg'}>
      {data?.title && <div className={'font-medium mb-2'}>{data.title}</div>}
      <div className={'grid grid-cols-[auto_1fr_auto] items-center gap-x-2 gap-y-1 text-sm'}>
        {items.map((item, i) => (
          <React.Fragment key={i}>
            <span className={'truncate max-w-40'}>{item.label}</span>
            <div className={'h-4 rounded-sm bg-muted overflow-hidden'}>
              <div className={'h-full rounded-sm bg-primary'}
                   style={{ width: `${max > 0 ? Math.min(100, Math.max(0, item.value / max * 100)) : 0}%` }} />
            </div>
            <span className={'tabular-nums text-muted-foreground'}>{item.value}{data?.unit ? ` ${data.unit}` : ''}</span>
          </React.Fragment>
        ))}
      </div>
    </div>
  )
}
