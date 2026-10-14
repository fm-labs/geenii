import { WidgetRendererProps } from '@/components/xchat/chat.types.ts'
import { CopyButton } from './copy-button.tsx'

const lineClass = (line: string) => {
  if (line.startsWith('+++') || line.startsWith('---')) return 'text-muted-foreground font-semibold'
  if (line.startsWith('@@')) return 'text-muted-foreground bg-muted/50'
  if (line.startsWith('+')) return 'bg-green-500/10 text-green-700 dark:text-green-400'
  if (line.startsWith('-')) return 'bg-destructive/10 text-destructive'
  return ''
}

/** geenii.diff — data: { diff: unified diff text, filename? }; the diff is computed by the sender */
export const DiffWidget = ({ data }: WidgetRendererProps<{ diff: string; filename?: string } | null>) => {
  const diff = data?.diff ?? ''
  const lines = diff.replace(/\n$/, '').split('\n')
  const added = lines.filter((l) => l.startsWith('+') && !l.startsWith('+++')).length
  const removed = lines.filter((l) => l.startsWith('-') && !l.startsWith('---')).length
  return (
    <div className={'rounded-md border overflow-hidden'}>
      <div className={'flex items-center justify-between gap-2 bg-muted px-3 py-1 text-xs text-muted-foreground'}>
        <span className={'truncate'}>
          {data?.filename || 'diff'}
          <span className={'ml-2 text-green-600'}>+{added}</span>
          <span className={'ml-1 text-destructive'}>-{removed}</span>
        </span>
        <CopyButton text={diff} />
      </div>
      <pre className={'text-xs py-2 overflow-x-auto max-h-96'}>
        {lines.map((line, i) => <div key={i} className={`px-3 ${lineClass(line)}`}>{line || ' '}</div>)}
      </pre>
    </div>
  )
}
