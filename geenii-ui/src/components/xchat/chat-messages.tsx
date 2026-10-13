import React from 'react'
import { cn } from 'cn'
import { useChat } from '@/components/xchat/chat-context.tsx'
import { ChatMessageRendererType } from '@/components/xchat/chat.types.ts'
import { buildToolCallIndex, ToolCallIndexContext } from '@/components/xchat/chat-tool-calls.ts'
import ChatMessage from '@/components/xchat/chat-message.tsx'

type ChatMessagesProps = {
  /** Replaces the message component; content parts are still customizable via the provider's renderers */
  messageRenderer?: ChatMessageRendererType
  /** Shown when there are no messages */
  empty?: React.ReactNode
  /** Keep the newest message in view while the user is at the bottom */
  autoScroll?: boolean
  className?: string
}

/** The nearest scrolling ancestor, or the document's scrolling element. */
const getScrollParent = (el: HTMLElement | null): HTMLElement => {
  for (let node = el?.parentElement; node; node = node.parentElement) {
    const { overflowY } = getComputedStyle(node)
    if ((overflowY === 'auto' || overflowY === 'scroll') && node.scrollHeight > node.clientHeight) return node
  }
  return (document.scrollingElement ?? document.documentElement) as HTMLElement
}

/**
 * ChatMessages component displays the list of chat messages.
 */
const ChatMessages = (props: ChatMessagesProps) => {
  const { messageRenderer: MessageRenderer = ChatMessage, empty, autoScroll = true, className } = props
  const messages = useChat((s) => s.messages)
  const toolCalls = React.useMemo(() => buildToolCallIndex(messages), [messages])

  const endRef = React.useRef<HTMLDivElement>(null)
  const stickToBottom = React.useRef(true)

  // only follow new messages if the user has not scrolled up
  React.useEffect(() => {
    if (!autoScroll) return
    const onScroll = () => {
      const scroller = getScrollParent(endRef.current)
      stickToBottom.current = scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight < 120
    }
    window.addEventListener('scroll', onScroll, { passive: true, capture: true })
    return () => window.removeEventListener('scroll', onScroll, { capture: true })
  }, [autoScroll])

  // scroll the container to its very end (not just the last message into view),
  // so that content after the list, like a sticky input, does not cover the newest message
  React.useEffect(() => {
    if (!autoScroll || !stickToBottom.current) return
    const scroller = getScrollParent(endRef.current)
    scroller.scrollTo({ top: scroller.scrollHeight })
  }, [messages, autoScroll])

  if (messages.length === 0 && empty) return <>{empty}</>

  return (
    <ToolCallIndexContext.Provider value={toolCalls}>
      <div className={cn('flex flex-col gap-4', className)} role={'log'} aria-live={'polite'}>
        {messages.map((message, idx) => (
          <MessageRenderer key={message.id} message={message} isLast={idx === messages.length - 1} />
        ))}
        <div ref={endRef} />
      </div>
    </ToolCallIndexContext.Provider>
  )
}

export default ChatMessages
