import { WidgetRendererProps } from '@/components/xchat/chat.types.ts'

const JsonValue = ({ value }: { value: unknown }) => {
  if (value === null) return <span className={'text-muted-foreground'}>null</span>
  if (typeof value === 'string') return <span className={'text-green-700 dark:text-green-400'}>"{value}"</span>
  if (typeof value === 'number') return <span className={'text-blue-700 dark:text-blue-400'}>{value}</span>
  if (typeof value === 'boolean') return <span className={'text-purple-700 dark:text-purple-400'}>{String(value)}</span>
  return <span>{String(value)}</span>
}

/** One key/value of the JSON tree; objects and arrays are collapsible */
const JsonNode = ({ name, value, depth, expand }: { name?: string; value: unknown; depth: number; expand: number }) => {
  const label = name != null && <span className={'text-muted-foreground'}>{name}: </span>
  if (value === null || typeof value !== 'object') {
    return <div className={'pl-4'}>{label}<JsonValue value={value} /></div>
  }
  const isArray = Array.isArray(value)
  const entries = isArray ? value.map((v, i) => [String(i), v] as const) : Object.entries(value)
  const summary = isArray ? `[${entries.length}]` : `{${entries.length}}`
  return (
    <details open={depth < expand} className={'pl-4 [&>summary]:-ml-4'}>
      <summary className={'cursor-pointer select-none'}>
        {label}<span className={'text-muted-foreground'}>{summary}</span>
      </summary>
      {entries.map(([key, v]) => <JsonNode key={key} name={key} value={v} depth={depth + 1} expand={expand} />)}
    </details>
  )
}

/** geenii.json — data: { value, title?, expand? = 2 }; expand is the number of levels opened initially */
export const JsonWidget = ({ data }: WidgetRendererProps<{ value: unknown; title?: string; expand?: number } | null>) => (
  <div className={'rounded-md border overflow-hidden'}>
    {data?.title && <div className={'bg-muted px-3 py-1 text-xs text-muted-foreground'}>{data.title}</div>}
    <div className={'font-mono text-xs p-2 overflow-auto max-h-96'}>
      <JsonNode value={data?.value ?? null} depth={0} expand={data?.expand ?? 2} />
    </div>
  </div>
)
