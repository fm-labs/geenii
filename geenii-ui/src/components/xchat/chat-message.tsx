import React from 'react'
import { cn } from 'cn'
import { ChatMessageRendererProps } from '@/components/xchat/chat.types.ts'
import ChatContentPart, { useIsPartVisible } from '@/components/xchat/chat-content-part.tsx'

const formatTime = (timestamp: string) => {
  const date = new Date(timestamp)
  return isNaN(date.getTime()) ? '' : date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

/**
 * One message: the envelope (sender, time, role styling) around its content parts.
 * Renders nothing if none of its parts is visible.
 */
const ChatMessage = ({ message }: ChatMessageRendererProps) => {
  const isPartVisible = useIsPartVisible()
  const parts = message.message.content.filter(isPartVisible)
  if (parts.length === 0) return null

  const role = message.message.role
  const isUser = role === 'user'

  if (message.message.type === 'system' || role === 'system') {
    return (
      <div className={'text-center text-xs text-muted-foreground italic py-1'} data-role={'system'}>
        {parts.map((part, i) => <ChatContentPart key={i} part={part} message={message} />)}
      </div>
    )
  }

  return (
    <div className={cn('group flex flex-col gap-1', isUser ? 'items-end' : 'items-start')} data-role={role}>
      <div className={'flex items-baseline gap-2 px-1 text-xs text-muted-foreground'}>
        {!isUser && <span className={'font-medium'}>{message.sender_id}</span>}
        <span className={'opacity-0 transition-opacity group-hover:opacity-100'}>{formatTime(message.timestamp)}</span>
      </div>
      <div className={cn(
        'flex flex-col gap-2 min-w-0',
        isUser
          ? 'max-w-[85%] rounded-2xl rounded-br-sm bg-primary text-primary-foreground px-4 py-2'
          : 'w-full',
      )}>
        {parts.map((part, i) => <ChatContentPart key={i} part={part} message={message} />)}
      </div>
    </div>
  )
}

export default ChatMessage
