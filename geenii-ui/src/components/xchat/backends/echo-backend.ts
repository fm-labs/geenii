import type {
  ChatBackend,
  ChatEvent,
  ChatMessage,
  ChatSendRequest,
  ContentPart,
  InteractionResponse,
  MessageRole,
  SystemMessageLevel,
} from '../chat.types.ts'
import {
  SAMPLE_FILE_TEXT,
  SAMPLE_MARKDOWN,
  SAMPLE_SYSTEM_MESSAGES,
  sampleBeepDataUrl,
  sampleSvgBase64,
  sampleSvgDataUrl,
  sampleTextFile,
  sampleEasterEggs,
  sampleWidgetMessages,
} from './echo-examples.ts'

export type EchoBackendOptions = {
  /** Simulated response latency in ms */
  delay?: number
  senderId?: string
}

/** Input that triggers the example turn (case-insensitive) */
export const ECHO_EXAMPLE_TRIGGER = 'example'

/** Input that triggers the widget turn (case-insensitive) */
export const ECHO_WIDGETS_TRIGGER = 'widgets'

const id = () => `${Date.now().toString(16)}${Math.random().toString(16).slice(2, 10)}`

const aborted = () => new DOMException('Aborted', 'AbortError')

const sleep = (ms: number, signal: AbortSignal) => new Promise<void>((resolve, reject) => {
  const timer = setTimeout(resolve, ms)
  signal.addEventListener('abort', () => {
    clearTimeout(timer)
    reject(aborted())
  }, { once: true })
})

/**
 * Local backend for demos and tests. Echoes text input back.
 *
 * - Input starting with "tool" simulates an agent tool call that needs approval:
 *   it emits an interaction, waits for `respond`, then emits the tool call result.
 * - Input "example" streams one message per content type (text, image, audio, file, embed, json,
 *   function, tool_call + tool_call_result, interaction, confirmation, widget) plus one system message per level.
 * - Input "widgets" streams only the widget examples: one system message per built-in widget.
 * - Hidden commands (not in listCommands): the easter eggs "matrix", "boot", "snake", "fortune", "dice",
 *   and "crash" (a widget that crashes after 3 s, to see the widget error boundary).
 */
export const createEchoBackend = (options: EchoBackendOptions = {}): ChatBackend => {
  const delay = options.delay ?? 500
  const senderId = options.senderId ?? 'echo'
  const waiting = new Map<string, (choice: string) => void>()

  const message = (contextId: string, role: MessageRole, content: ContentPart[], level: SystemMessageLevel = 'info'): ChatMessage => {
    const messageId = id()
    const timestamp = new Date().toISOString()
    return {
      id: messageId,
      timestamp,
      sender_id: role === 'system' ? 'system' : senderId,
      context_id: contextId,
      message: role === 'system'
        ? { type: 'system', id: messageId, role: 'system', level, content, timestamp }
        : { type: 'message', id: messageId, role, content, timestamp },
    }
  }

  const say = (contextId: string, role: MessageRole, ...content: ContentPart[]): ChatEvent =>
    ({ type: 'message', message: message(contextId, role, content) })

  const notify = (contextId: string, level: SystemMessageLevel, text: string): ChatEvent =>
    ({ type: 'message', message: message(contextId, 'system', [{ type: 'text', text }], level) })

  const system = (contextId: string, level: SystemMessageLevel, content: ContentPart[]): ChatEvent =>
    ({ type: 'message', message: message(contextId, 'system', content, level) })

  /** Wait until `respond` answers the interaction/confirmation with this id. */
  const waitForAnswer = (interactionId: string, signal: AbortSignal) => new Promise<string>((resolve, reject) => {
    waiting.set(interactionId, resolve)
    signal.addEventListener('abort', () => {
      waiting.delete(interactionId)
      reject(aborted())
    }, { once: true })
  })

  async function* toolTurn(contextId: string, text: string, signal: AbortSignal): AsyncIterable<ChatEvent> {
    const callId = id()
    const args = { text }
    yield say(contextId, 'assistant', {
      type: 'interaction',
      interaction_id: callId,
      interaction_type: 'tool_call_request',
      text: `Requesting approval to call tool 'echo' with arguments ${JSON.stringify(args)}.`,
      choices: ['Allow', 'Deny'],
    })
    yield { type: 'status', status: 'awaiting_input' }
    const choice = await waitForAnswer(callId, signal)

    yield { type: 'status', status: 'tool' }
    await sleep(delay, signal)
    const allowed = choice === 'Allow'
    yield say(contextId, 'tool', {
      type: 'tool_call_result',
      call_id: callId,
      name: 'echo',
      arguments: args,
      result: allowed ? { echo: text } : { error: 'Tool execution rejected.' },
    })
    yield { type: 'status', status: 'thinking' }
    await sleep(delay, signal)
    yield say(contextId, 'assistant', { type: 'text', text: allowed ? `Tool said: ${text}` : 'Ok, not calling the tool.' })
  }

  /** One system message per built-in widget (easter eggs included), in groups led by a text message */
  async function* widgetTurn(contextId: string, signal: AbortSignal): AsyncIterable<ChatEvent> {
    for (const { level, content } of sampleWidgetMessages()) {
      yield system(contextId, level, content)
      await sleep(Math.max(50, delay / 6), signal)
    }
  }

  async function* exampleTurn(contextId: string, signal: AbortSignal): AsyncIterable<ChatEvent> {
    const step = Math.max(50, delay / 3)
    const pause = () => sleep(step, signal)
    const file = sampleTextFile()

    yield notify(contextId, 'info', 'Example turn: one message per content type.')
    await pause()
    for (const { level, text } of SAMPLE_SYSTEM_MESSAGES) {
      yield notify(contextId, level, text)
    }
    await pause()
    yield say(contextId, 'assistant', { type: 'text', text: SAMPLE_MARKDOWN })
    await pause()
    yield say(contextId, 'assistant',
      { type: 'text', text: 'An **image** from a URL and one from base64:' },
      { type: 'image', url: sampleSvgDataUrl('image (url)', '#6366f1'), alt: 'Sample image from a URL' },
      { type: 'image', base64: sampleSvgBase64('image (base64)', '#0ea5e9', 240, 135), alt: 'Sample image from base64' },
    )
    await pause()
    yield say(contextId, 'assistant',
      { type: 'text', text: 'An **audio** clip:' },
      { type: 'audio', url: sampleBeepDataUrl(), duration: 0.6 },
    )
    await pause()
    yield say(contextId, 'assistant',
      { type: 'text', text: 'A **file**:' },
      { type: 'file', url: file.url, filename: 'hello.txt', content_type: 'text/plain', size: file.size },
    )
    await pause()
    yield say(contextId, 'assistant', {
      type: 'embed',
      title: 'An embed',
      description: 'Link previews show a title, a description and a thumbnail.',
      url: 'https://example.com',
      thumbnail_url: sampleSvgDataUrl('embed', '#f59e0b', 128, 128),
    })
    await pause()
    yield say(contextId, 'assistant', {
      type: 'json',
      data: { kind: 'json', nested: { list: [1, 2, 3], ok: true }, text: SAMPLE_FILE_TEXT.trim() },
    })
    await pause()
    yield* widgetTurn(contextId, signal)
    await pause()
    yield say(contextId, 'assistant', { type: 'function', name: 'get_time', arguments: { tz: 'UTC' }, result: new Date().toISOString() })
    await pause()

    // a tool call whose result arrives later: the card shows "running", then fills in the result
    const callId = id()
    yield say(contextId, 'assistant', { type: 'tool_call', name: 'add', arguments: { a: 2, b: 3 }, call_id: callId })
    yield { type: 'status', status: 'tool' }
    await sleep(delay * 2, signal)
    yield say(contextId, 'tool', { type: 'tool_call_result', name: 'add', arguments: { a: 2, b: 3 }, call_id: callId, result: 5 })
    await pause()
    // a result without a call message, as the agent sends it, and a failed one
    yield say(contextId, 'tool', { type: 'tool_call_result', name: 'read_file', arguments: { path: 'notes.md' }, call_id: id(), result: { lines: 42 } })
    yield say(contextId, 'tool', { type: 'tool_call_result', name: 'delete_file', arguments: { path: '/' }, call_id: id(), error: 'Permission denied' })
    yield { type: 'status', status: 'thinking' }
    await pause()

    const interactionId = id()
    yield say(contextId, 'assistant', {
      type: 'interaction',
      interaction_id: interactionId,
      interaction_type: 'choice',
      text: 'An interaction: pick a color.',
      choices: ['Red', 'Green', 'Blue'],
    })
    yield { type: 'status', status: 'awaiting_input' }
    const color = await waitForAnswer(interactionId, signal)

    const confirmationId = id()
    yield say(contextId, 'assistant', {
      type: 'confirmation',
      confirmation_id: confirmationId,
      text: `A confirmation: use ${color}?`,
    })
    yield { type: 'status', status: 'awaiting_input' }
    const confirmed = ['yes', 'confirm', 'confirmed'].includes((await waitForAnswer(confirmationId, signal)).toLowerCase())

    yield { type: 'status', status: 'thinking' }
    await pause()
    yield say(contextId, 'assistant', {
      type: 'text',
      text: confirmed ? `Done. You picked **${color}**.` : `Ok, not using ${color}.`,
    })
  }

  async function* send(request: ChatSendRequest, signal: AbortSignal): AsyncIterable<ChatEvent> {
    const contextId = request.contextId || id()
    if (!request.contextId) yield { type: 'context', contextId }

    yield { type: 'status', status: 'thinking' }
    await sleep(delay, signal)

    const text = request.content
      .map((p) => (p.type === 'text' ? p.text : `[${p.type}]`))
      .join(' ')
    // the triggers work with and without a leading slash (slash commands)
    const command = text.trim().toLowerCase().replace(/^\//, '')
    // hidden commands, not in listCommands
    const easterEggs = sampleEasterEggs()
    const easterEgg = Object.prototype.hasOwnProperty.call(easterEggs, command) ? easterEggs[command] : null

    if (easterEgg) {
      yield system(contextId, easterEgg.level, easterEgg.content)
    } else if (command === ECHO_EXAMPLE_TRIGGER) {
      yield* exampleTurn(contextId, signal)
    } else if (command === ECHO_WIDGETS_TRIGGER) {
      yield* widgetTurn(contextId, signal)
    } else if (command.startsWith('tool')) {
      yield* toolTurn(contextId, text, signal)
    } else {
      yield say(contextId, 'assistant', { type: 'text', text: `You said: ${text}` })
    }

    yield { type: 'done' }
  }

  return {
    id: 'echo',
    capabilities: { streaming: true, interactions: true, files: false, history: false, models: false },
    send,
    listCommands: async () => [
      { command: ECHO_EXAMPLE_TRIGGER, description: 'Stream one example message of each content type' },
      { command: ECHO_WIDGETS_TRIGGER, description: 'Stream one system message per built-in widget' },
      { command: 'tool', description: 'Simulate a tool call that needs your approval' },
    ],
    respond: async (_contextId: string, response: InteractionResponse) => {
      const resolve = waiting.get(response.interactionId)
      if (!resolve) throw new Error(`No pending interaction ${response.interactionId}`)
      waiting.delete(response.interactionId)
      resolve(response.choice)
    },
  }
}
