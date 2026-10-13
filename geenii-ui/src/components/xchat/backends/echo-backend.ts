import type {
  ChatBackend,
  ChatEvent,
  ChatMessage,
  ChatSendRequest,
  ContentPart,
  InteractionResponse,
} from '../chat.types.ts'

export type EchoBackendOptions = {
  /** Simulated response latency in ms */
  delay?: number
  senderId?: string
}

const id = () => `${Date.now().toString(16)}${Math.random().toString(16).slice(2, 10)}`

const sleep = (ms: number, signal: AbortSignal) => new Promise<void>((resolve, reject) => {
  const timer = setTimeout(resolve, ms)
  signal.addEventListener('abort', () => {
    clearTimeout(timer)
    reject(new DOMException('Aborted', 'AbortError'))
  }, { once: true })
})

/**
 * Local backend for demos and tests. Echoes text input back.
 *
 * Input starting with "tool" simulates an agent tool call that needs approval:
 * it emits an interaction, waits for `respond`, then emits the tool call result.
 */
export const createEchoBackend = (options: EchoBackendOptions = {}): ChatBackend => {
  const delay = options.delay ?? 500
  const senderId = options.senderId ?? 'echo'
  const waiting = new Map<string, (choice: string) => void>()

  const message = (contextId: string, role: 'assistant' | 'tool', content: ContentPart[]): ChatMessage => {
    const messageId = id()
    const timestamp = new Date().toISOString()
    return {
      id: messageId,
      timestamp,
      sender_id: senderId,
      context_id: contextId,
      message: { type: 'message', id: messageId, role, content, timestamp },
    }
  }

  async function* send(request: ChatSendRequest, signal: AbortSignal): AsyncIterable<ChatEvent> {
    const contextId = request.contextId || id()
    if (!request.contextId) yield { type: 'context', contextId }

    yield { type: 'status', status: 'thinking' }
    await sleep(delay, signal)

    const text = request.content
      .map((p) => (p.type === 'text' ? p.text : `[${p.type}]`))
      .join(' ')

    if (text.toLowerCase().startsWith('tool')) {
      const callId = id()
      const args = { text }
      yield {
        type: 'message',
        message: message(contextId, 'assistant', [{
          type: 'interaction',
          interaction_id: callId,
          interaction_type: 'tool_call_request',
          text: `Requesting approval to call tool 'echo' with arguments ${JSON.stringify(args)}.`,
          choices: ['Allow', 'Deny'],
        }]),
      }
      yield { type: 'status', status: 'awaiting_input' }

      const choice = await new Promise<string>((resolve, reject) => {
        waiting.set(callId, resolve)
        signal.addEventListener('abort', () => {
          waiting.delete(callId)
          reject(new DOMException('Aborted', 'AbortError'))
        }, { once: true })
      })

      yield { type: 'status', status: 'tool' }
      await sleep(delay, signal)
      const allowed = choice === 'Allow'
      yield {
        type: 'message',
        message: message(contextId, 'tool', [{
          type: 'tool_call_result',
          call_id: callId,
          name: 'echo',
          arguments: args,
          result: allowed ? { echo: text } : { error: 'Tool execution rejected.' },
        }]),
      }
      yield { type: 'status', status: 'thinking' }
      await sleep(delay, signal)
      yield {
        type: 'message',
        message: message(contextId, 'assistant', [{ type: 'text', text: allowed ? `Tool said: ${text}` : 'Ok, not calling the tool.' }]),
      }
    } else {
      yield { type: 'message', message: message(contextId, 'assistant', [{ type: 'text', text: `You said: ${text}` }]) }
    }

    yield { type: 'done' }
  }

  return {
    id: 'echo',
    capabilities: { streaming: true, interactions: true, files: false, history: false, models: false },
    send,
    respond: async (_contextId: string, response: InteractionResponse) => {
      const resolve = waiting.get(response.interactionId)
      if (!resolve) throw new Error(`No pending interaction ${response.interactionId}`)
      waiting.delete(response.interactionId)
      resolve(response.choice)
    },
  }
}
