import { joinUrl } from '@/lib/utils.ts'
import type {
  ChatBackend,
  ChatEvent,
  ChatMessage,
  ChatSendRequest,
  ChatSessionInfo,
  InteractionResponse,
} from '../chat.types.ts'

export type AgentBackendOptions = {
  /** Server base URL, e.g. ServerContext.serverUrl */
  baseUrl: string
  /** Agent for new conversations (default "default") */
  agent?: string
  headers?: Record<string, string>
}

/** An HTTP error with the server's Problem body ({error, status, detail}). */
export class ChatApiError extends Error {
  readonly status: number
  readonly response: { status: number; data: unknown }

  constructor(status: number, data: any) {
    super(data?.detail || data?.error || `Request failed with status ${status}`)
    this.name = 'ChatApiError'
    this.status = status
    // same shape as axios errors, so errorMessage() finds the Problem detail
    this.response = { status, data }
  }
}

const toError = async (res: Response): Promise<ChatApiError> => {
  let data: unknown = null
  try {
    data = await res.json()
  } catch {
    // not a Problem body
  }
  return new ChatApiError(res.status, data)
}

/** Parse an NDJSON response body into objects, one per line. */
async function* readNdjson(body: ReadableStream<Uint8Array>): AsyncGenerator<any> {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      let newline: number
      while ((newline = buffer.indexOf('\n')) >= 0) {
        const line = buffer.slice(0, newline).trim()
        buffer = buffer.slice(newline + 1)
        if (line) yield JSON.parse(line)
      }
    }
    buffer += decoder.decode()
    if (buffer.trim()) yield JSON.parse(buffer)
  } finally {
    reader.releaseLock()
  }
}

const toChatEvent = (event: any): ChatEvent | null => {
  switch (event?.type) {
    case 'message':
      return { type: 'message', message: event.message as ChatMessage }
    case 'status':
      return { type: 'status', status: event.status }
    case 'error':
      return { type: 'error', error: event.error }
    case 'done':
      return { type: 'done' }
    default:
      console.warn('Unknown chat stream event', event)
      return null
  }
}

/**
 * Backend for the agent chat API (/api/v1/chats, see src/geenii/server/chat_routes.py).
 *
 * Each conversation is a server-side session with its own agent; a turn is streamed as NDJSON.
 * Tool approvals are answered via `respond`. Aborting a turn also cancels it on the server.
 */
export const createAgentBackend = (options: AgentBackendOptions): ChatBackend => {
  const agent = options.agent ?? 'default'
  const base = joinUrl(options.baseUrl, 'api/v1/chats')

  const request = async (method: string, path: string, body?: unknown, signal?: AbortSignal): Promise<Response> => {
    const res = await fetch(`${base}${path}`, {
      method,
      headers: { ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}), ...options.headers },
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal,
    })
    if (!res.ok) throw await toError(res)
    return res
  }

  const json = async <T>(method: string, path: string, body?: unknown): Promise<T> =>
    (await request(method, path, body)).json()

  async function* send(req: ChatSendRequest, signal: AbortSignal): AsyncIterable<ChatEvent> {
    let contextId = req.contextId
    if (!contextId) {
      const info = await json<ChatSessionInfo>('POST', '', { agent })
      contextId = info.id
      yield { type: 'context', contextId }
    }

    const res = await request('POST', `/${contextId}/messages`, { content: req.content }, signal)
    if (!res.body) throw new Error('Empty response from chat API')

    // closing the stream alone does not stop an agent that waits for a tool approval
    const id = contextId
    const onAbort = () => {
      fetch(`${base}/${id}/cancel`, { method: 'POST', headers: options.headers }).catch(() => undefined)
    }
    signal.addEventListener('abort', onAbort, { once: true })
    try {
      for await (const raw of readNdjson(res.body)) {
        const event = toChatEvent(raw)
        if (!event) continue
        yield event
        if (event.type === 'done') return
      }
    } finally {
      signal.removeEventListener('abort', onAbort)
    }
  }

  return {
    id: `agent:${agent}`,
    capabilities: { streaming: true, interactions: true, files: false, history: true, models: false },
    send,
    respond: async (contextId: string, response: InteractionResponse) => {
      await request('POST', `/${contextId}/interactions/${encodeURIComponent(response.interactionId)}`,
        { choice: response.choice })
    },
    loadHistory: (contextId: string) => json<ChatMessage[]>('GET', `/${contextId}/messages`),
    listSessions: () => json<ChatSessionInfo[]>('GET', ''),
    deleteSession: async (contextId: string) => {
      await request('DELETE', `/${contextId}`)
    },
  }
}
