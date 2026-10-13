import React from 'react'
import { LoaderIcon, HandIcon } from 'lucide-react'
import { cn } from 'cn'
import { useChat } from '@/components/xchat/chat-context.tsx'
import { ChatActivity } from '@/components/xchat/chat.types.ts'

const DEFAULT_LABELS: Record<ChatActivity, string> = {
  thinking: 'Thinking',
  tool: 'Running tool',
  awaiting_input: 'Waiting for your input',
}

/**
 * Shows what the agent is doing while a turn runs. Renders nothing when idle.
 */
const ChatStatus = ({ labels, className }: { labels?: Partial<Record<ChatActivity, string>>; className?: string }) => {
  const { status, activity } = useChat((s) => ({ status: s.status, activity: s.activity }))
  if (status === 'idle' || status === 'error') return null

  const current: ChatActivity = status === 'awaiting_input' ? 'awaiting_input' : activity ?? 'thinking'
  const label = labels?.[current] ?? DEFAULT_LABELS[current]

  return (
    <div className={cn('flex items-center gap-2 text-sm text-muted-foreground', className)} role={'status'}>
      {current === 'awaiting_input'
        ? <HandIcon className={'size-4 text-amber-600'} />
        : <LoaderIcon className={'size-4 animate-spin'} />}
      <span>{label}</span>
    </div>
  )
}

export default ChatStatus
