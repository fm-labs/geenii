import { WidgetRendererProps } from '@/components/xchat/chat.types.ts'
import { CopyButton } from './copy-button.tsx'

/** geenii.code — data: { code, language?, filename? }; no syntax highlighting */
export const CodeWidget = ({ data }: WidgetRendererProps<{ code: string; language?: string; filename?: string } | null>) => (
  <div className={'rounded-md border overflow-hidden'}>
    <div className={'flex items-center justify-between gap-2 bg-muted px-3 py-1 text-xs text-muted-foreground'}>
      <span className={'truncate'}>{data?.filename || data?.language || 'code'}</span>
      <CopyButton text={data?.code ?? ''} />
    </div>
    <pre className={'text-xs p-3 overflow-x-auto max-h-96'}><code>{data?.code}</code></pre>
  </div>
)
