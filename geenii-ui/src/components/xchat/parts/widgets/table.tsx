import { WidgetRendererProps } from '@/components/xchat/chat.types.ts'

type TableData = { columns?: string[]; rows: (unknown[] | Record<string, unknown>)[] }

export const cell = (value: unknown) => (value == null ? '' : typeof value === 'object' ? JSON.stringify(value) : String(value))

/** geenii.table — data: { columns?: string[], rows: (array | object)[] }; columns default to the keys of object rows */
export const TableWidget = ({ data }: WidgetRendererProps<TableData | null>) => {
  const rows = Array.isArray(data?.rows) ? data.rows : []
  const columns = data?.columns ?? [...new Set(rows.flatMap((row) => (Array.isArray(row) ? [] : Object.keys(row))))]
  return (
    <div className={'overflow-x-auto max-h-96 rounded-md border'}>
      <table className={'text-sm w-full'}>
        {columns.length > 0 && (
          <thead className={'bg-muted'}>
            <tr>{columns.map((col) => <th key={col} className={'px-2 py-1 text-left font-medium'}>{col}</th>)}</tr>
          </thead>
        )}
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className={'border-t'}>
              {(Array.isArray(row) ? row : columns.map((col) => row[col])).map((value, j) => (
                <td key={j} className={'px-2 py-1'}>{cell(value)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
