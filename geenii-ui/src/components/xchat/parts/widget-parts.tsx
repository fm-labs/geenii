import { OutputDataMarkdown } from '@/components/output-data-markdown.tsx'
import { useChatWidgets } from '@/components/xchat/chat-context.tsx'
import { ContentPartRendererProps, WidgetContent } from '@/components/xchat/chat.types.ts'
import { JsonBlock, markdownClass } from './media-parts.tsx'
import { defaultWidgets } from './widgets/index.ts'

export * from './widgets/index.ts'

/** Shown for widgets the UI does not know */
export const WidgetFallback = ({ part }: { part: WidgetContent }) => {
  if (part.text) {
    return <div className={markdownClass}><OutputDataMarkdown data={part.text} /></div>
  }
  return (
    <div className={'text-sm text-muted-foreground'}>
      <div className={'italic'}>[widget: {part.name}]</div>
      {part.data != null && <JsonBlock data={part.data} />}
    </div>
  )
}

/** Renders a widget part with the widget registered under its name, or its fallback text, below its title. */
export const WidgetPart = ({ part, message }: ContentPartRendererProps<WidgetContent>) => {
  const widgets = useChatWidgets()
  const Widget = widgets[part.name] ?? defaultWidgets[part.name]
  const body = Widget ? <Widget data={part.data ?? null} part={part} message={message} /> : <WidgetFallback part={part} />
  if (!part.title) return body
  return (
    <div className={'flex min-w-0 flex-col gap-1'} data-widget={part.name}>
      <div className={'text-xs font-medium text-muted-foreground'}>{part.title}</div>
      {body}
    </div>
  )
}
