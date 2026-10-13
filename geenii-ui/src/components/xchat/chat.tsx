import React from 'react'
import { cn } from 'cn'
import ChatMessages from '@/components/xchat/chat-messages.tsx'
import ChatStatus from '@/components/xchat/chat-status.tsx'
import ChatError from '@/components/xchat/chat-error.tsx'
import ChatInput from '@/components/xchat/chat-input.tsx'
import ChatModelSelector from '@/components/xchat/chat-model-selector.tsx'
import ChatCommandMenu from '@/components/xchat/chat-command-menu.tsx'
import { useChat } from '@/components/xchat/chat-context.tsx'

/**
 * Default composition of the xchat parts. Must be used within a ChatProvider.
 *
 * Without messages the input is centered (below `empty`); once there are messages it sticks to the bottom
 * of the scroll container. Give it a height (e.g. `className="min-h-svh"`) so it can center.
 * For other layouts, compose the parts directly.
 */
const Chat = ({ placeholder, empty, inputAddons, footer, className }: {
  placeholder?: string
  /** Shown above the centered input while there are no messages */
  empty?: React.ReactNode
  /** Rendered in the input toolbar, e.g. <ChatVoiceInput /> */
  inputAddons?: React.ReactNode
  /** Rendered below the input */
  footer?: React.ReactNode
  className?: string
}) => {
  const hasMessages = useChat((s) => s.messages.length > 0)

  // the input keeps its position in the tree in both states, so it is not remounted (keeps focus)
  return (
    <div className={cn('flex flex-col', !hasMessages && 'justify-center', className)}>
      {hasMessages
        ? <ChatMessages className={'flex-1 pt-4 pb-2'} />
        : <div className={'pb-4'}>{empty}</div>}
      <div className={cn(
        'flex flex-col gap-2 bg-background',
        hasMessages && 'sticky bottom-0 z-10 pt-2 pb-4',
      )}>
        <ChatStatus />
        <ChatError />
        <ChatInput placeholder={placeholder}>
          <ChatCommandMenu />
          {inputAddons}
        </ChatInput>
        <ChatModelSelector className={'max-w-64'} />
        {footer}
      </div>
    </div>
  )
}

export default Chat
