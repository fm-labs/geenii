import React from 'react'
import { useChat, useChatActions } from '@/components/xchat/chat-context.tsx'
import { errorMessage } from '@/components/xchat/chat-session.ts'
import { ChatMessage, ChatSessionState } from '@/components/xchat/chat.types.ts'

const isBusy = (s: ChatSessionState) => s.status === 'submitting' || s.status === 'streaming' || s.status === 'awaiting_input'

/** The text of a user message (its text parts, joined) */
export const messageText = (message: ChatMessage) =>
  message.message.content.map((p) => (p.type === 'text' ? p.text : '')).join('\n').trim()

/**
 * For widgets that answer in the chat: `reply(text)` sends a plain user message.
 * - `busy`: a turn is running, so sending is not possible right now (the session allows one turn at a time)
 * - `answer`: the first user message after the widget's message, if any. Derived from the chat history,
 *   so it also holds after reloading a conversation. Any later user message counts, also a typed one.
 */
export const useChatReply = (message: ChatMessage) => {
  const { send } = useChatActions()
  const busy = useChat(isBusy)
  const answer = useChat((s) => {
    const index = s.messages.findIndex((m) => m.id === message.id)
    return index < 0 ? null : s.messages.slice(index + 1).find((m) => m.message.role === 'user') ?? null
  })
  const [error, setError] = React.useState<string | null>(null)

  /** Send `text` as a user message; false (and `error` set) if it could not be sent */
  const reply = async (text: string): Promise<boolean> => {
    setError(null)
    try {
      await send(text)
      return true
    } catch (err) {
      setError(errorMessage(err))
      return false
    }
  }

  return { reply, busy, answer, error }
}
