import React from 'react'
import { ChatMessage, ContentPart, ContentPartRendererProps } from '@/components/xchat/chat.types.ts'
import { useContentPartRenderers } from '@/components/xchat/chat-context.tsx'
import { useToolCallIndex } from '@/components/xchat/chat-tool-calls.ts'
import { defaultRenderers, UnknownPart } from '@/components/xchat/parts'

/** Whether a part is rendered at all (results of rendered tool calls are shown by the call). */
export const useIsPartVisible = () => {
  const { calls } = useToolCallIndex()
  return (part: ContentPart) => !(part.type === 'tool_call_result' && part.call_id && calls.has(part.call_id))
}

/**
 * Renders one content part with the renderer for its type: the provider's override, else the default.
 */
const ChatContentPart = ({ part, message }: { part: ContentPart; message: ChatMessage }) => {
  const overrides = useContentPartRenderers()
  const { results } = useToolCallIndex()

  const Renderer = (overrides[part.type] ?? defaultRenderers[part.type]) as
    React.ComponentType<ContentPartRendererProps> | undefined
  if (!Renderer) return <UnknownPart part={part} />

  const result = part.type === 'tool_call' && part.call_id ? results.get(part.call_id) : undefined
  return <Renderer part={part} message={message} result={result} />
}

export default ChatContentPart
