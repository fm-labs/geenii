import { WidgetRendererProps } from '@/components/xchat/chat.types.ts'

/**
 * geenii.html — data: { html: string, height?: number, title?: string }
 * Rendered in a sandboxed iframe: scripts run, but in an opaque origin without access to the app.
 */
export const HtmlWidget = ({ data }: WidgetRendererProps<{ html: string; height?: number; title?: string } | null>) => (
  <iframe
    srcDoc={data?.html ?? ''}
    sandbox={'allow-scripts'}
    title={data?.title ?? 'HTML widget'}
    style={{ height: data?.height ?? 240 }}
    className={'w-full rounded-md border bg-white'}
  />
)
