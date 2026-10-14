import { WidgetRendererProps } from '@/components/xchat/chat.types.ts'
import { ChildContent, ChildContentData } from './child-content.tsx'

type GridItem = ChildContentData & { wide?: boolean }

type GridData = { columns?: number; min_width?: number; items: GridItem[] }

const GAP = 8 // px, gap-2

/**
 * geenii.grid — data: { columns? = 2, min_width? = 200, items: { widget?, text?, wide? }[] }
 * Nested widgets side by side: up to `columns` (1–4) per row, fewer when a column would get
 * narrower than `min_width` px, down to one column on narrow screens. `wide` items take a whole row.
 */
export const GridWidget = ({ data, message }: WidgetRendererProps<GridData | null>) => {
  const items = (Array.isArray(data?.items) ? data.items : []).filter((i): i is GridItem => i != null && typeof i === 'object')
  if (items.length === 0) return <div className={'text-sm text-muted-foreground'}>Empty grid</div>

  const columns = Math.min(4, Math.max(1, Math.round(data?.columns ?? 2)))
  const minWidth = Math.max(80, data?.min_width ?? 200)
  // auto-fill tracks at least min_width wide and at least 1/columns of the row, so a row never holds more
  // than `columns`; min(100%, …) lets a single column shrink below min_width instead of overflowing
  const track = `minmax(min(100%, max(${minWidth}px, calc((100% - ${(columns - 1) * GAP}px) / ${columns}))), 1fr)`

  return (
    <div className={'grid min-w-0 gap-2'} style={{ gridTemplateColumns: `repeat(auto-fill, ${track})` }}>
      {items.map((item, i) => (
        <div key={i} className={'min-w-0'} style={item.wide ? { gridColumn: '1 / -1' } : undefined}>
          {item.widget ? <ChildContent item={item} message={message} />
            : <div className={'h-full rounded-md border p-3'}><ChildContent item={item} message={message} /></div>}
        </div>
      ))}
    </div>
  )
}
