import { OutputDataMarkdown } from '@/components/output-data-markdown.tsx'
import { ChatMessage, WidgetContent } from '@/components/xchat/chat.types.ts'
import { markdownClass } from '@/components/xchat/parts/media-parts.tsx'
// circular (widget-parts → widgets/index → layout widget → child-content → widget-parts),
// fine: WidgetPart is only used while rendering
import { WidgetPart } from '@/components/xchat/parts/widget-parts.tsx'

/** A widget nested in a layout widget (tabs, grid, accordion): a widget content part without `type` */
export type ChildWidget = { name: string; data?: unknown; heading?: string | null; text?: string | null }

/** What a layout widget's tab, cell or section holds: a nested widget, else markdown `text` */
export type ChildContentData = { widget?: ChildWidget; text?: string }

/**
 * Renders a nested widget through `WidgetPart` (lookup, heading, fallback, its own error boundary),
 * or markdown `text`, or `empty` when there is neither.
 */
export const ChildContent = ({ item, message, empty = 'Empty' }: { item: ChildContentData; message: ChatMessage; empty?: string }) => {
  const widget = item.widget
  if (widget && typeof widget.name === 'string') {
    const part: WidgetContent = { type: 'widget', name: widget.name, data: widget.data, heading: widget.heading, text: widget.text }
    return <WidgetPart part={part} message={message} />
  }
  if (typeof item.text === 'string' && item.text) {
    return <div className={markdownClass}><OutputDataMarkdown data={item.text} /></div>
  }
  return <div className={'text-sm text-muted-foreground'}>{empty}</div>
}
