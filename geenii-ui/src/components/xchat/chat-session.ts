import type {
  ChatBackend,
  ChatEvent,
  ChatMessage,
  ChatSessionActions,
  ChatSessionState,
  ContentPart,
  InteractionResponse,
  PendingInteraction,
} from './chat.types.ts'

export type ChatSessionOptions = {
  backend: ChatBackend
  contextId?: string | null
  initialMessages?: ChatMessage[]
  model?: string | null
  /** sender_id of messages typed by the user */
  userId?: string
  onError?: (error: string) => void
}

type Listener = () => void

export const newId = (): string =>
  typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID().replace(/-/g, '')
    : `${Date.now().toString(16)}${Math.random().toString(16).slice(2)}`

/** Human-readable error text; understands the backend's Problem body ({error, status, detail}) on axios errors. */
export const errorMessage = (err: unknown): string => {
  const e = err as any
  return e?.response?.data?.detail || e?.response?.data?.error || e?.message || String(err) || 'Unknown error'
}

const isAbortError = (err: unknown) => (err as any)?.name === 'AbortError'

/**
 * Framework-agnostic state of one chat conversation.
 *
 * Holds the messages and turn status, and drives a ChatBackend. React binds to it via
 * `subscribe`/`getState` (useSyncExternalStore), so the store itself is plain TypeScript.
 * State is replaced immutably on every change; never mutate the object returned by getState().
 */
export class ChatSession implements ChatSessionActions {
  private state: ChatSessionState
  private readonly listeners = new Set<Listener>()
  private backend: ChatBackend
  private readonly userId: string
  private readonly onError?: (error: string) => void
  private turn: AbortController | null = null
  private loadToken = 0

  constructor(options: ChatSessionOptions) {
    this.backend = options.backend
    this.userId = options.userId ?? 'user'
    this.onError = options.onError
    this.state = {
      contextId: options.contextId ?? null,
      messages: options.initialMessages ?? [],
      status: 'idle',
      activity: null,
      pendingInteractions: {},
      error: null,
      model: options.model ?? null,
    }
  }

  // -- store ----------------------------------------------------------------

  subscribe = (listener: Listener): (() => void) => {
    this.listeners.add(listener)
    return () => {
      this.listeners.delete(listener)
    }
  }

  getState = (): ChatSessionState => this.state

  getBackend = (): ChatBackend => this.backend

  get isBusy(): boolean {
    return this.turn !== null
  }

  private setState(update: Partial<ChatSessionState> | ((state: ChatSessionState) => Partial<ChatSessionState>)) {
    const patch = typeof update === 'function' ? update(this.state) : update
    this.state = { ...this.state, ...patch }
    this.listeners.forEach((listener) => listener())
  }

  private fail(err: unknown) {
    const error = errorMessage(err)
    this.setState({ status: 'error', activity: null, error })
    this.onError?.(error)
  }

  /** Swap the backend. A running turn is cancelled and a new conversation starts (context ids are per backend). */
  setBackend(backend: ChatBackend) {
    if (backend === this.backend) return
    this.cancel()
    this.backend = backend
    this.loadToken++
    this.setState({ contextId: null, messages: [], pendingInteractions: {}, status: 'idle', activity: null, error: null })
  }

  // -- actions --------------------------------------------------------------

  send = async (input: string | ContentPart[]): Promise<void> => {
    const content: ContentPart[] = typeof input === 'string'
      ? (input.trim() ? [{ type: 'text', text: input.trim() }] : [])
      : input
    if (content.length === 0) return
    if (this.turn) throw new Error('A message is already being processed')

    const turn = new AbortController()
    this.turn = turn

    const messageId = newId()
    const timestamp = new Date().toISOString()
    const userMessage: ChatMessage = {
      id: messageId,
      timestamp,
      sender_id: this.userId,
      context_id: this.state.contextId,
      message: { type: 'message', id: messageId, role: 'user', content, timestamp },
    }
    this.setState((s) => ({
      messages: [...s.messages, userMessage],
      status: 'submitting',
      activity: 'thinking',
      error: null,
    }))

    try {
      const events = this.backend.send(
        { contextId: this.state.contextId, messageId, content, model: this.state.model },
        turn.signal,
      )
      for await (const event of events) {
        if (turn.signal.aborted || event.type === 'done') break
        this.handleEvent(event)
      }
      if (!turn.signal.aborted) {
        // the turn is over, so nothing on the backend waits for an answer anymore
        this.setState((s) => ({ status: s.status === 'error' ? 'error' : 'idle', activity: null, pendingInteractions: {} }))
      }
    } catch (err) {
      if (!turn.signal.aborted && !isAbortError(err)) this.fail(err)
    } finally {
      if (this.turn === turn) this.turn = null
    }
  }

  cancel = (): void => {
    if (!this.turn) return
    this.turn.abort()
    this.turn = null
    this.setState({ status: 'idle', activity: null, pendingInteractions: {} })
  }

  respond = async (response: InteractionResponse): Promise<void> => {
    const { interactionId, choice } = response
    const { contextId, pendingInteractions } = this.state
    if (!pendingInteractions[interactionId]) throw new Error(`No pending interaction ${interactionId}`)
    if (!this.backend.respond) throw new Error(`Backend '${this.backend.id}' does not support interactions`)

    // record the choice on the interaction part, so renderers show the answer
    this.setState((s) => {
      const { [interactionId]: _answered, ...rest } = s.pendingInteractions
      return {
        pendingInteractions: rest,
        status: Object.keys(rest).length > 0 ? 'awaiting_input' : (this.turn ? 'streaming' : 'idle'),
        activity: this.turn ? 'tool' : null,
        messages: s.messages.map((m) => withInteractionChoice(m, interactionId, choice)),
      }
    })

    try {
      await this.backend.respond(contextId, response)
    } catch (err) {
      this.fail(err)
      throw err
    }
  }

  clear = (): void => {
    this.cancel()
    this.setState({ messages: [], pendingInteractions: {}, status: 'idle', activity: null, error: null })
  }

  load = async (contextId: string | null): Promise<void> => {
    this.cancel()
    const token = ++this.loadToken
    this.setState({ contextId, messages: [], pendingInteractions: {}, status: 'idle', activity: null, error: null })
    if (!contextId || !this.backend.loadHistory) return

    try {
      const messages = await this.backend.loadHistory(contextId)
      if (token === this.loadToken) this.setState({ messages })
    } catch (err) {
      if (token === this.loadToken) this.fail(err)
    }
  }

  setModel = (model: string | null): void => {
    this.setState({ model })
  }

  dismissError = (): void => {
    this.setState((s) => ({ error: null, status: s.status === 'error' ? (this.turn ? 'streaming' : 'idle') : s.status }))
  }

  // -- events ---------------------------------------------------------------

  private handleEvent(event: ChatEvent) {
    switch (event.type) {
      case 'message':
        this.setState((s) => receiveMessage(s, event.message))
        break
      case 'context':
        this.setState({ contextId: event.contextId })
        break
      case 'status':
        this.setState((s) => ({
          activity: event.status,
          status: event.status === 'awaiting_input' || Object.keys(s.pendingInteractions).length > 0
            ? 'awaiting_input'
            : 'streaming',
        }))
        break
      case 'error':
        this.fail(event.error)
        break
    }
  }
}

/** Add or replace (same id) a message and update pending interactions from its content. */
const receiveMessage = (s: ChatSessionState, message: ChatMessage): Partial<ChatSessionState> => {
  const index = s.messages.findIndex((m) => m.id === message.id)
  const messages = index === -1
    ? [...s.messages, message]
    : s.messages.map((m, i) => (i === index ? message : m))

  const pending: Record<string, PendingInteraction> = { ...s.pendingInteractions }
  for (const part of message.message.content) {
    if (part.type === 'interaction') {
      if (part.choice == null) pending[part.interaction_id] = part
      else delete pending[part.interaction_id]
    } else if (part.type === 'confirmation') {
      if (part.confirmed == null) pending[part.confirmation_id] = part
      else delete pending[part.confirmation_id]
    } else if (part.type === 'tool_call_result' && part.call_id) {
      // a tool approval's interaction_id is the tool call_id; once the result is in, it was answered
      delete pending[part.call_id]
    }
  }

  const awaiting = Object.keys(pending).length > 0
  return {
    messages,
    pendingInteractions: pending,
    status: awaiting ? 'awaiting_input' : 'streaming',
    activity: awaiting ? 'awaiting_input' : s.activity,
    contextId: s.contextId ?? message.context_id ?? null,
  }
}

/** Choices that answer a confirmation with "confirmed" */
export const CONFIRM_CHOICES = ['yes', 'confirm', 'confirmed', 'allow', 'true']

const answerPart = (part: ContentPart, interactionId: string, choice: string): ContentPart => {
  if (part.type === 'interaction' && part.interaction_id === interactionId) return { ...part, choice }
  if (part.type === 'confirmation' && part.confirmation_id === interactionId) {
    return { ...part, confirmed: CONFIRM_CHOICES.includes(choice.toLowerCase()) }
  }
  return part
}

const withInteractionChoice = (message: ChatMessage, interactionId: string, choice: string): ChatMessage => {
  const content = message.message.content
  const answered = content.map((p) => answerPart(p, interactionId, choice))
  if (answered.every((p, i) => p === content[i])) return message
  return { ...message, message: { ...message.message, content: answered } }
}
