import React from 'react'
import { AlertCircleIcon, AlertTriangleIcon, InfoIcon } from 'lucide-react'
import { cn } from 'cn'
import { ChatMessageRendererProps, SystemMessageLevel } from '@/components/xchat/chat.types.ts'
import ChatContentPart, { useIsPartVisible } from '@/components/xchat/chat-content-part.tsx'
import ChatMessageUsage from '@/components/xchat/chat-message-usage.tsx'

const SYSTEM_LEVEL_STYLES: Record<SystemMessageLevel, { icon: typeof InfoIcon, className: string }> = {
  info: { icon: InfoIcon, className: 'border-transparent text-muted-foreground' },
  warning: { icon: AlertTriangleIcon, className: 'border-amber-500/50 bg-amber-500/5 text-amber-700 dark:text-amber-400' },
  error: { icon: AlertCircleIcon, className: 'border-destructive/50 bg-destructive/5 text-destructive' },
}

// system messages with a widget are full-width cards; widgets keep the normal text size and color
const SYSTEM_CARD_STYLES: Record<SystemMessageLevel, string> = {
  info: 'border-border bg-muted/30',
  warning: 'border-amber-500/50 bg-amber-500/5',
  error: 'border-destructive/50 bg-destructive/5',
}

const SYSTEM_CARD_ICON_STYLES: Record<SystemMessageLevel, string> = {
  info: 'text-muted-foreground',
  warning: 'text-amber-700 dark:text-amber-400',
  error: 'text-destructive',
}

const formatTime =(timestamp: string) => {
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
  // usage of the model call behind this message (only on the first message of each call)
  const usage = message.message.type === 'message' ? message.message.usage : null

  if (message.message.type === 'system' || role === 'system') {
    // messages stored before the level field existed have none
    const level = (message.message.type === 'system' && message.message.level) || 'info'
    const { icon: Icon, className } = SYSTEM_LEVEL_STYLES[level]
    if (parts.some((part) => part.type === 'widget')) {
      return (
        <div role={level === 'info' ? 'status' : 'alert'} data-role={'system'} data-level={level}
             className={cn('flex w-full items-start gap-2 rounded-md border px-3 py-2 text-sm', SYSTEM_CARD_STYLES[level])}>
          {/* info cards need no icon; warnings and errors keep theirs */}
          {level !== 'info' && <Icon className={cn('size-4 shrink-0 mt-0.5', SYSTEM_CARD_ICON_STYLES[level])} />}
          <div className={'flex min-w-0 flex-1 flex-col gap-2 break-words'}>
            {parts.map((part, i) => <ChatContentPart key={i} part={part} message={message} />)}
          </div>
        </div>
      )
    }
    return (
      <div className={'flex justify-center py-1'} data-role={'system'} data-level={level}>
        <div role={level === 'info' ? 'status' : 'alert'}
             className={cn('flex max-w-[85%] items-start gap-1.5 rounded-md border px-2.5 py-1 text-xs', className)}>
          <Icon className={'size-3.5 shrink-0 mt-px'} />
          <div className={'min-w-0 break-words'}>
            {parts.map((part, i) => <ChatContentPart key={i} part={part} message={message} />)}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className={cn('group flex flex-col gap-1', isUser ? 'items-end' : 'items-start')} data-role={role}>
      <div className={'flex items-baseline gap-2 px-1 text-xs text-muted-foreground'}>
        {!isUser && <span className={'font-medium'}>{message.sender_id}</span>}
        <span className={'opacity-0 transition-opacity group-hover:opacity-100'}>{formatTime(message.timestamp)}</span>
        {!isUser && usage && <ChatMessageUsage usage={usage} />}
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
