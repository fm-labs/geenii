import React, { PropsWithChildren } from 'react'
import { ChatContext, ChatRenderersContext, ChatWidgetsContext } from './chat-context.tsx'
import { ChatSession } from '@/components/xchat/chat-session.ts'
import { ChatBackend, ChatMessage, ContentPartRenderers, WidgetRenderers } from '@/components/xchat/chat.types.ts'

export type ChatProviderProps = PropsWithChildren<{
  backend: ChatBackend
  /** Conversation to open. Changing it loads that conversation; null starts a new one. */
  contextId?: string | null
  /** Messages to start with. Only read on mount; use the session's `load` to switch conversations. */
  initialMessages?: ChatMessage[]
  model?: string | null
  userId?: string
  /** Per content-type renderer overrides */
  renderers?: ContentPartRenderers
  /** Widget components by name; added to (and overriding) the built-in widgets */
  widgets?: WidgetRenderers
  onError?: (error: string) => void
}>

/**
 * Creates one ChatSession and shares it with all xchat components below.
 */
const ChatProvider = (props: ChatProviderProps) => {
  const { backend, contextId, model, renderers, widgets, onError, children } = props

  const onErrorRef = React.useRef(onError)
  onErrorRef.current = onError

  const [session] = React.useState(() => new ChatSession({
    backend,
    contextId,
    model,
    initialMessages: props.initialMessages,
    userId: props.userId,
    onError: (error) => onErrorRef.current?.(error),
  }))

  React.useEffect(() => {
    session.setBackend(backend)
  }, [session, backend])

  React.useEffect(() => {
    if (contextId !== undefined && contextId !== session.getState().contextId) {
      session.load(contextId)
    }
  }, [session, contextId])

  React.useEffect(() => {
    if (model !== undefined) session.setModel(model)
  }, [session, model])

  // stop a running turn when the chat goes away
  React.useEffect(() => () => session.cancel(), [session])

  const emptyRenderers = React.useMemo(() => ({}), [])

  return (
    <ChatContext.Provider value={session}>
      <ChatRenderersContext.Provider value={renderers ?? emptyRenderers}>
        <ChatWidgetsContext.Provider value={widgets ?? emptyRenderers}>
          {children}
        </ChatWidgetsContext.Provider>
      </ChatRenderersContext.Provider>
    </ChatContext.Provider>
  )
}

export { ChatProvider }
export default ChatProvider
