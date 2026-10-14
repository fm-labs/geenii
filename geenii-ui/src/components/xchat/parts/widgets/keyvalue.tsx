import React from 'react'
import { WidgetRendererProps } from '@/components/xchat/chat.types.ts'
import { JsonBlock } from '@/components/xchat/parts/media-parts.tsx'
import { cell } from './table.tsx'

type KeyValueData = { title?: string; items: { key: string; value: unknown }[] } | Record<string, unknown>

/** geenii.keyvalue — data: { title?, items: { key, value }[] } or a plain object */
export const KeyValueWidget = ({ data }: WidgetRendererProps<KeyValueData | null>) => {
  const listed = Array.isArray(data?.items)
  const title = listed ? (data.title as string | undefined) : undefined
  const items = listed
    ? (data.items as { key: string; value: unknown }[])
    : Object.entries(data ?? {}).map(([key, value]) => ({ key, value }))
  return (
    <div className={'rounded-md border p-3 max-w-lg'}>
      {title && <div className={'font-medium mb-2'}>{title}</div>}
      <dl className={'grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm'}>
        {items.map(({ key, value }, i) => (
          <React.Fragment key={i}>
            <dt className={'text-muted-foreground'}>{key}</dt>
            <dd className={'min-w-0 break-words'}>
              {value != null && typeof value === 'object' ? <JsonBlock data={value} /> : cell(value)}
            </dd>
          </React.Fragment>
        ))}
      </dl>
    </div>
  )
}
