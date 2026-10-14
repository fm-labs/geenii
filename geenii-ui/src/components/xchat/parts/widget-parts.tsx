import React from 'react'
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

type WidgetErrorBoundaryProps = React.PropsWithChildren<{ part: WidgetContent }>

/**
 * Catches errors thrown while rendering a widget (e.g. on malformed data) and shows the part's fallback
 * instead, so one broken widget does not take down the chat. Resets when the part changes.
 */
export class WidgetErrorBoundary extends React.Component<WidgetErrorBoundaryProps, { error: Error | null }> {
  state = { error: null as Error | null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  componentDidCatch(error: Error) {
    console.warn(`Widget '${this.props.part.name}' failed to render`, error)
  }

  componentDidUpdate(prevProps: WidgetErrorBoundaryProps) {
    if (this.state.error && prevProps.part !== this.props.part) this.setState({ error: null })
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <div className={'flex flex-col gap-1'} data-widget-error={this.props.part.name}>
        <WidgetFallback part={this.props.part} />
        <div className={'text-xs text-muted-foreground italic'}>Widget {this.props.part.name} could not be displayed.</div>
      </div>
    )
  }
}

/** Renders a widget part with the widget registered under its name, or its fallback text, below its heading. */
export const WidgetPart = ({ part, message }: ContentPartRendererProps<WidgetContent>) => {
  const widgets = useChatWidgets()
  const Widget = widgets[part.name] ?? defaultWidgets[part.name]
  const body = Widget
    ? <WidgetErrorBoundary part={part}><Widget data={part.data ?? null} part={part} message={message} /></WidgetErrorBoundary>
    : <WidgetFallback part={part} />
  if (!part.heading) return body
  return (
    <div className={'flex min-w-0 flex-col gap-1'} data-widget={part.name}>
      <div className={'text-xs font-medium text-muted-foreground'}>{part.heading}</div>
      {body}
    </div>
  )
}
