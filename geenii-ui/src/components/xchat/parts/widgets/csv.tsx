import React from 'react'
import { WidgetRendererProps } from '@/components/xchat/chat.types.ts'
import { TableWidget } from './table.tsx'

/** Guess the delimiter from the first line: the most frequent of , ; tab | */
const detectDelimiter = (csv: string) => {
  const line = csv.split('\n', 1)[0]
  return [',', ';', '\t', '|'].reduce((best, d) => (line.split(d).length > line.split(best).length ? d : best), ',')
}

/** Parse CSV (RFC 4180: quoted fields, "" escapes, newlines in quotes) into rows of fields */
export const parseCsv = (csv: string, delimiter = detectDelimiter(csv)): string[][] => {
  const rows: string[][] = []
  let row: string[] = []
  let field = ''
  let quoted = false
  for (let i = 0; i < csv.length; i++) {
    const c = csv[i]
    if (quoted) {
      if (c === '"' && csv[i + 1] === '"') { field += '"'; i++ }
      else if (c === '"') quoted = false
      else field += c
    } else if (c === '"' && field === '') quoted = true
    else if (c === delimiter) { row.push(field); field = '' }
    else if (c === '\n' || c === '\r') {
      if (c === '\r' && csv[i + 1] === '\n') i++
      row.push(field); rows.push(row); row = []; field = ''
    } else field += c
  }
  if (field !== '' || row.length > 0) { row.push(field); rows.push(row) }
  return rows.filter((r) => r.length > 1 || r[0] !== '')
}

/** geenii.csv — data: { csv, delimiter? (detected), header? = true, title? }; rendered as a table */
export const CsvWidget = (props: WidgetRendererProps<{ csv: string; delimiter?: string; header?: boolean; title?: string } | null>) => {
  const { data } = props
  const rows = React.useMemo(() => parseCsv(data?.csv ?? '', data?.delimiter || undefined), [data?.csv, data?.delimiter])
  const [columns, ...body] = data?.header === false ? [undefined, ...rows] : rows
  return (
    <div className={'space-y-1'}>
      {data?.title && <div className={'font-medium'}>{data.title}</div>}
      <TableWidget {...props} data={{ columns, rows: body }} />
    </div>
  )
}
