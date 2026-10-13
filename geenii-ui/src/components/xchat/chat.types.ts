import type { ComponentType, JSX } from 'react'

// ---------------------------------------------------------------------------
// Wire format
//
// Mirrors the backend models 1:1:
//   content parts  -> src/geenii/chat_models.py (ContentPart)
//   messages       -> src/geenii/datamodels.py  (ModelMessage, SystemMessage, WireMessage, ChatMessage)
//
// Pydantic serializes unset optional fields as `null` and datetimes as ISO 8601 strings,
// hence `?: T | null` and `timestamp: string`.
// ---------------------------------------------------------------------------

/** ISO 8601 datetime string, e.g. "2026-10-13T12:34:56.789Z" */
export type IsoDateTime = string

export type TextContent = {
  type: 'text'
  text: string
}

export type ImageContent = {
  type: 'image'
  url?: string | null
  base64?: string | null
  alt?: string | null
}

export type AudioContent = {
  type: 'audio'
  url: string
  duration?: number | null
}

export type FileContent = {
  type: 'file'
  url: string
  filename: string
  content_type?: string | null
  size?: number | null
}

export type EmbedContent = {
  type: 'embed'
  title?: string | null
  description?: string | null
  url?: string | null
  thumbnail_url?: string | null
  video_url?: string | null
}

export type FunctionCallContent = {
  type: 'function'
  name: string
  arguments?: Record<string, unknown> | null
  result?: string | null
}

export type ToolCallContent = {
  type: 'tool_call'
  name: string
  arguments?: Record<string, unknown> | null
  /** Unique call ID, links the call to its ToolCallResultContent */
  call_id?: string | null
  /** True, if HITL approval is required before executing the tool */
  require_approval?: boolean
  approval_id?: string | null
}

export type ToolCallResultContent = {
  type: 'tool_call_result'
  call_id?: string | null
  name: string
  arguments?: Record<string, unknown> | null
  result?: unknown
  /** Error message if the tool call failed */
  error?: string | null
}

export type JsonContent = {
  type: 'json'
  data: Record<string, unknown> | unknown[]
}

export type UserInteractionContent = {
  type: 'interaction'
  interaction_id: string
  /** e.g. "tool_call_request"; for tool approvals interaction_id equals the tool call_id */
  interaction_type: string
  text: string
  choices: string[]
  /** The user's choice, once answered */
  choice?: string | null
}

export type UserConfirmationContent = {
  type: 'confirmation'
  confirmation_id: string
  text: string
  /** true = confirmed, false = rejected, null = not answered yet */
  confirmed?: boolean | null
}

export type ContentPart =
  | TextContent
  | ImageContent
  | AudioContent
  | FileContent
  | EmbedContent
  | FunctionCallContent
  | ToolCallContent
  | ToolCallResultContent
  | JsonContent
  | UserInteractionContent
  | UserConfirmationContent

export type ContentPartType = ContentPart['type']

/** Narrow a ContentPart union member by its `type` discriminator. */
export type ContentPartOf<T extends ContentPartType> = Extract<ContentPart, { type: T }>

export type MessageRole = 'user' | 'assistant' | 'system' | 'tool'

/** A message from/to a model (backend: ModelMessage) */
export type ModelMessage = {
  type: 'message'
  id: string
  role: MessageRole
  content: ContentPart[]
  timestamp: IsoDateTime
}

/** A server-generated notification (backend: SystemMessage) */
export type SystemMessage = {
  type: 'system'
  id: string
  role: 'system'
  content: ContentPart[]
  timestamp: IsoDateTime
}

export type WireMessage = ModelMessage | SystemMessage

/** Chat message envelope (backend: ChatMessage) */
export type ChatMessage = {
  id: string
  timestamp: IsoDateTime
  /** "user" for user messages, otherwise the agent / bot name */
  sender_id: string
  message: WireMessage
  context_id?: string | null
}

// ---------------------------------------------------------------------------
// Backend adapter
//
// The exchangeable part: components and the session store only talk to a ChatBackend,
// never to HTTP directly. A backend may answer in one batch or stream events.
// ---------------------------------------------------------------------------

export type ChatBackendCapabilities = {
  /** Events arrive incrementally while the agent is working */
  streaming: boolean
  /** Supports answering interactions / tool approvals via `respond` */
  interactions: boolean
  /** Supports file uploads */
  files: boolean
  /** Supports loading the message history of an existing context via `loadHistory` */
  history: boolean
  /** The client can choose the model per request */
  models: boolean
}

export type ChatSendRequest = {
  /** Omit to start a new conversation; the backend reports the new id via a `context` event */
  contextId?: string | null
  /** ID of the user message the session already added; a backend that echoes it back must reuse this id */
  messageId: string
  content: ContentPart[]
  model?: string | null
}

export type ChatActivity = 'thinking' | 'tool' | 'awaiting_input'

export type ChatEvent =
  | { type: 'message'; message: ChatMessage }
  | { type: 'context'; contextId: string }
  | { type: 'status'; status: ChatActivity }
  | { type: 'error'; error: string }
  | { type: 'done' }

export type InteractionResponse = {
  interactionId: string
  choice: string
}

export type ChatSessionInfo = {
  id: string
  title?: string | null
  agent?: string | null
  created_at?: IsoDateTime | null
  updated_at?: IsoDateTime | null
}

export interface ChatBackend {
  readonly id: string
  readonly capabilities: ChatBackendCapabilities

  /** Send user input. Yields events until the turn is finished; aborting the signal cancels the turn. */
  send(request: ChatSendRequest, signal: AbortSignal): AsyncIterable<ChatEvent>

  /** Answer a pending interaction (e.g. allow/deny a tool call). Requires `capabilities.interactions`. */
  respond?(contextId: string, response: InteractionResponse): Promise<void>

  /** Requires `capabilities.history`. */
  loadHistory?(contextId: string): Promise<ChatMessage[]>

  listSessions?(): Promise<ChatSessionInfo[]>

  deleteSession?(contextId: string): Promise<void>

  /** Requires `capabilities.files`. Returns content parts to attach to the next message. */
  uploadFiles?(contextId: string, files: File[]): Promise<FileContent[]>
}

/** Wraps a backend, e.g. to handle slash commands client-side. */
export type ChatBackendMiddleware = (backend: ChatBackend) => ChatBackend

// ---------------------------------------------------------------------------
// Session state (shared chat context)
// ---------------------------------------------------------------------------

export type ChatStatus =
  | 'idle'
  | 'submitting'      // request sent, nothing received yet
  | 'streaming'       // events are arriving
  | 'awaiting_input'  // the agent waits for an interaction response
  | 'error'

/** A question the user has not answered yet, keyed by interaction_id / confirmation_id */
export type PendingInteraction = UserInteractionContent | UserConfirmationContent

export type ChatSessionState = {
  contextId: string | null
  messages: ChatMessage[]
  status: ChatStatus
  /** Latest activity reported by the backend while busy */
  activity: ChatActivity | null
  /** Unanswered interactions, keyed by interaction_id */
  pendingInteractions: Record<string, PendingInteraction>
  error: string | null
  model: string | null
}

export type ChatSessionActions = {
  send(input: string | ContentPart[]): Promise<void>
  cancel(): void
  respond(response: InteractionResponse): Promise<void>
  clear(): void
  /** Switch to (and load the history of) another context; null starts a new conversation */
  load(contextId: string | null): Promise<void>
  setModel(model: string | null): void
  /** Clear the error and leave the 'error' status */
  dismissError(): void
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

export type ChatMessageRendererProps = {
  message: ChatMessage
  isLast?: boolean
}

export type ChatMessageRendererType = (props: ChatMessageRendererProps) => JSX.Element

export type ContentPartRendererProps<T extends ContentPart = ContentPart> = {
  part: T
  message: ChatMessage
  /** For tool_call parts: the matching tool_call_result (same call_id), if already received */
  result?: ToolCallResultContent
}

/** Per-type renderer overrides; missing types fall back to the default renderers. */
export type ContentPartRenderers = {
  [K in ContentPartType]?: ComponentType<ContentPartRendererProps<ContentPartOf<K>>>
}

// ---------------------------------------------------------------------------
// Type guards
// ---------------------------------------------------------------------------

export const isPartType = <T extends ContentPartType>(part: ContentPart, type: T): part is ContentPartOf<T> =>
  part.type === type

export const isModelMessage = (message: WireMessage): message is ModelMessage => message.type === 'message'

export const isSystemMessage = (message: WireMessage): message is SystemMessage => message.type === 'system'
