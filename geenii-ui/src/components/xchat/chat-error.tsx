import React from 'react'
import { AlertCircleIcon, XIcon } from 'lucide-react'
import { cn } from 'cn'
import { useChat, useChatActions } from '@/components/xchat/chat-context.tsx'

/**
 * Shows the last error of the session, dismissable. Renders nothing without an error.
 */
const ChatError = ({ className }: { className?: string }) => {
  const error = useChat((s) => s.error)
  const { dismissError } = useChatActions()
  if (!error) return null

  return (
    <div role={'alert'}
         className={cn('flex items-start gap-2 rounded-md border border-destructive/50 bg-destructive/5 px-3 py-2 text-sm text-destructive', className)}>
      <AlertCircleIcon className={'size-4 shrink-0 mt-0.5'} />
      <div className={'flex-1 break-words'}>{error}</div>
      <button type={'button'} aria-label={'Dismiss'} onClick={dismissError} className={'opacity-70 hover:opacity-100'}>
        <XIcon className={'size-4'} />
      </button>
    </div>
  )
}

export default ChatError
