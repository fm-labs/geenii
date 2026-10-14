import { WidgetRendererProps } from '@/components/xchat/chat.types.ts'

type TreemapItem = { label: string; value?: number; color?: string; children?: TreemapItem[] }

type TreemapData = { title?: string; unit?: string; items: TreemapItem[] }

export type Rect = { x: number; y: number; w: number; h: number }

const COLORS = ['var(--chart-1)', 'var(--chart-2)', 'var(--chart-3)', 'var(--chart-4)', 'var(--chart-5)']

// layout units; the container has the same aspect ratio, so tiles come out as square as the layout made them
const W = 160, H = 90

const format = (n: number) => (Number.isInteger(n) ? n.toLocaleString() : n.toLocaleString(undefined, { maximumFractionDigits: 1 }))

/**
 * Squarified treemap layout (Bruls, Huizing, van Wijk): splits `rect` into one rectangle per value,
 * in the given order, with areas proportional to the values. Pass values sorted largest first.
 */
export const squarify = (values: number[], rect: Rect): Rect[] => {
  const total = values.reduce((sum, v) => sum + v, 0)
  if (total <= 0 || rect.w <= 0 || rect.h <= 0) return values.map(() => ({ ...rect, w: 0, h: 0 }))
  const areas = values.map((v) => v / total * rect.w * rect.h)
  const out: Rect[] = []
  let { x, y, w, h } = rect

  // worst aspect ratio of a row of areas laid along a side of length `side`
  const worst = (row: number[], side: number) => {
    const sum = row.reduce((s, a) => s + a, 0)
    return Math.max(side * side * Math.max(...row) / (sum * sum), sum * sum / (side * side * Math.min(...row)))
  }

  // lays the row along the shorter side and shrinks the remaining rectangle
  const place = (row: number[]) => {
    const sum = row.reduce((s, a) => s + a, 0)
    if (w >= h) {
      const width = sum / h
      let top = y
      for (const a of row) { out.push({ x, y: top, w: width, h: a / width }); top += a / width }
      x += width; w -= width
    } else {
      const height = sum / w
      let left = x
      for (const a of row) { out.push({ x: left, y, w: a / height, h: height }); left += a / height }
      y += height; h -= height
    }
  }

  let row: number[] = []
  for (const area of areas) {
    const side = Math.min(w, h)
    if (row.length > 0 && worst([...row, area], side) > worst(row, side)) {
      place(row)
      row = []
    }
    row.push(area)
  }
  if (row.length > 0) place(row)
  return out
}

const valueOf = (item: TreemapItem): number => (Array.isArray(item.children) && item.children.length > 0
  ? item.children.reduce((sum, c) => sum + valueOf(c), 0)
  : Number.isFinite(item.value) && item.value! > 0 ? item.value! : 0)

/** items with a positive value, largest first */
const clean = (items: unknown): TreemapItem[] => (Array.isArray(items) ? items : [])
  .filter((i): i is TreemapItem => typeof i?.label === 'string')
  .map((i) => ({ ...i, children: i.children ? clean(i.children) : undefined }))
  .filter((i) => valueOf(i) > 0)
  .sort((a, b) => valueOf(b) - valueOf(a))

type Tile = { rect: Rect; item: TreemapItem; color: string; path: string; strength: number }

/**
 * geenii.treemap — data: { title?, unit?, items: { label, value?, color?, children? }[] }
 * Nested rectangles sized by value, e.g. disk usage or a budget. An item with `children` (one level)
 * is split into its children, shaded in the item's colour; its value is the sum of theirs.
 */
export const TreemapWidget = ({ data }: WidgetRendererProps<TreemapData | null>) => {
  const items = clean(data?.items)
  if (items.length === 0) return <div className={'text-sm text-muted-foreground'}>No data</div>

  const total = items.reduce((sum, i) => sum + valueOf(i), 0)
  const unit = data?.unit ? ` ${data.unit}` : ''
  const tiles: Tile[] = []
  squarify(items.map(valueOf), { x: 0, y: 0, w: W, h: H }).forEach((rect, i) => {
    const item = items[i]
    const color = item.color || COLORS[i % COLORS.length]
    const children = item.children ?? []
    if (children.length === 0) {
      tiles.push({ rect, item, color, path: item.label, strength: 85 })
      return
    }
    squarify(children.map(valueOf), rect).forEach((childRect, j) => tiles.push({
      rect: childRect,
      item: children[j],
      color: children[j].color || color,
      path: `${item.label} / ${children[j].label}`,
      strength: 95 - j / Math.max(1, children.length - 1) * 30, // largest child lightest, the rest darker
    }))
  })

  return (
    <div className={'max-w-lg rounded-md border p-3'}>
      {data?.title && <div className={'mb-2 font-medium'}>{data.title}</div>}
      <div className={'relative w-full overflow-hidden rounded-sm'} style={{ aspectRatio: `${W} / ${H}` }}
           role={'img'} aria-label={items.map((i) => `${i.label}: ${format(valueOf(i))}${unit}`).join(', ')}>
        {tiles.map(({ rect, item, color, path, strength }, i) => {
          const value = valueOf(item)
          const big = rect.w > 14 && rect.h > 9
          return (
            <div key={i} title={`${path}: ${format(value)}${unit} (${+(value / total * 100).toFixed(1)}%)`}
                 className={'absolute overflow-hidden border border-background p-1 text-[11px] leading-tight text-white'}
                 style={{
                   left: `${rect.x / W * 100}%`, top: `${rect.y / H * 100}%`,
                   width: `${rect.w / W * 100}%`, height: `${rect.h / H * 100}%`,
                   background: `color-mix(in oklch, ${color} ${strength}%, black)`,
                 }}>
              {big && (
                <>
                  <div className={'truncate font-medium'}>{item.label}</div>
                  <div className={'truncate tabular-nums opacity-80'}>{format(value)}{unit}</div>
                </>
              )}
            </div>
          )
        })}
      </div>
      <div className={'mt-2 text-xs tabular-nums text-muted-foreground'}>Total {format(total)}{unit}</div>
    </div>
  )
}
