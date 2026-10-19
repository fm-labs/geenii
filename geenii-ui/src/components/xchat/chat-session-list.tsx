import React from 'react'
import { MessageSquarePlusIcon, TrashIcon } from 'lucide-react'
import { cn } from 'cn'
import { Button } from '@/components/ui/button.tsx'
import { useChat, useChatActions, useChatBackend } from '@/components/xchat/chat-context.tsx'
import { errorMessage } from '@/components/xchat/chat-session.ts'
import { ChatSessionInfo } from '@/components/xchat/chat.types.ts'

export type ChatSessionsState = {
  /** The backend can list conversations */
  supported: boolean
  /** The backend can delete conversations */
  canDelete: boolean
  sessions: ChatSessionInfo[]
  activeId: string | null
  error: string | null
  /** Open a conversation; null starts a new one */
  open: (contextId: string | null) => Promise<void>
  remove: (contextId: string) => Promise<void>
  refresh: () => Promise<void>
}

/**
 * The backend's conversations, for building session lists in any layout.
 * Refreshes after each turn (a new conversation may have been created) and when the conversation changes.
 */
export const useChatSessions = (): ChatSessionsState => {
  const { load } = useChatActions()
  const { contextId, status } = useChat((s) => ({ contextId: s.contextId, status: s.status }))
  const backend = useChatBackend()
  const [sessions, setSessions] = React.useState<ChatSessionInfo[]>([])
  const [error, setError] = React.useState<string | null>(null)

  const refresh = React.useCallback(async () => {
    if (!backend.listSessions) {
      setSessions([])
      return
    }
    try {
      setSessions(await backend.listSessions())
      setError(null)
    } catch (err) {
      setError(errorMessage(err))
    }
  }, [backend])

  React.useEffect(() => {
    if (status === 'idle') refresh()
  }, [refresh, status, contextId])

  const remove = React.useCallback(async (id: string) => {
    try {
      await backend.deleteSession?.(id)
      if (id === contextId) await load(null)
      await refresh()
    } catch (err) {
      setError(errorMessage(err))
    }
  }, [backend, contextId, load, refresh])

  return {
    supported: Boolean(backend.listSessions),
    canDelete: Boolean(backend.deleteSession),
    sessions,
    activeId: contextId,
    error,
    open: load,
    remove,
    refresh,
  }
}

/**
 * Lists the backend's conversations and switches between them. Renders nothing if the backend has no listSessions.
 */
const ChatSessionList = ({ className }: { className?: string }) => {
  const backend = useChatBackend()
  const { supported, canDelete, sessions, activeId, error, open, remove } = useChatSessions()
  if (!supported) return null

  const filtered = React.useMemo(() =>
    sessions.filter((s) =>
      s.agent === backend.id.substring('agent:'.length)
    ), [sessions, backend.id])

  return (
    <div className={cn('flex flex-col gap-1 text-sm', className)}>
      <Button variant={'outline'} size={'sm'} className={'justify-start'} onClick={() => open(null)}>
        <MessageSquarePlusIcon /> New chat
      </Button>
      {error && <div className={'text-destructive text-xs px-2'}>{error}</div>}
      {filtered.map((s) => (
        <div key={s.id}
             className={cn('group flex items-center rounded-md hover:bg-accent', s.id === activeId && 'bg-accent font-medium')}>
          <button type={'button'} className={'flex min-w-0 flex-1 flex-col px-2 py-1.5 text-left'} onClick={() => open(s.id)}>
            <span className={'truncate'}>{s.title || s.id}</span>
            {s.agent && <span className={'truncate text-xs font-normal text-muted-foreground'}>{s.agent}</span>}
          </button>
          {canDelete && (
            <button type={'button'} aria-label={'Delete chat'} onClick={() => remove(s.id)}
                    className={'px-2 opacity-0 group-hover:opacity-70 hover:opacity-100'}>
              <TrashIcon className={'size-3.5'} />
            </button>
          )}
        </div>
      ))}
    </div>
  )
}

export default ChatSessionList
