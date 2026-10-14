import React from 'react'
import { ChatSession } from '@/components/xchat/chat-session.ts'
import {
  ChatBackend,
  ChatSessionActions,
  ChatSessionState,
  ContentPartRenderers,
  WidgetRenderers,
} from '@/components/xchat/chat.types.ts'

/**
 * The shared chat context: every xchat component below a ChatProvider talks to the same ChatSession.
 */
export const ChatContext = React.createContext<ChatSession | null>(null)

export const ChatRenderersContext = React.createContext<ContentPartRenderers>({})

export const ChatWidgetsContext = React.createContext<WidgetRenderers>({})

export const useChatSession = (): ChatSession => {
  const session = React.useContext(ChatContext)
  if (!session) {
    throw new Error('useChatSession must be used within a ChatProvider')
  }
  return session
}

/**
 * Subscribe to (a slice of) the chat state. The component re-renders only when the selected value changes.
 *
 * The selector may derive new objects/arrays: its result is cached per state snapshot.
 *
 * @example const messages = useChat(s => s.messages)
 */
export function useChat(): ChatSessionState
export function useChat<T>(selector: (state: ChatSessionState) => T): T
export function useChat<T>(selector?: (state: ChatSessionState) => T): T | ChatSessionState {
  const session = useChatSession()
  const cache = React.useRef<{ state: ChatSessionState; selector: unknown; value: unknown } | null>(null)

  const getSnapshot = () => {
    const state = session.getState()
    if (!selector) return state
    if (cache.current?.state !== state || cache.current.selector !== selector) {
      cache.current = { state, selector, value: selector(state) }
    }
    return cache.current.value as T
  }

  return React.useSyncExternalStore(session.subscribe, getSnapshot, getSnapshot)
}

/** The session's current backend, e.g. to check its capabilities. Re-renders when the backend is swapped. */
export const useChatBackend = (): ChatBackend => {
  const session = useChatSession()
  return React.useSyncExternalStore(session.subscribe, session.getBackend, session.getBackend)
}

/** The chat actions (send, cancel, respond, …). Stable across renders; using it does not subscribe to state. */
export const useChatActions = (): ChatSessionActions => useChatSession()

export const useContentPartRenderers = (): ContentPartRenderers => React.useContext(ChatRenderersContext)

/** Widget components registered on the ChatProvider (without the built-in ones). */
export const useChatWidgets = (): WidgetRenderers => React.useContext(ChatWidgetsContext)
