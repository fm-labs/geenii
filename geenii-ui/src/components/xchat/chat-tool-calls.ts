import React from 'react'
import type { ChatMessage, ToolCallContent, ToolCallResultContent } from '@/components/xchat/chat.types.ts'

/**
 * Links tool calls to their results across messages (by call_id).
 *
 * The agent sends a tool call and its result as separate messages. The tool_call renderer shows the result inline,
 * so a result whose call is rendered elsewhere is hidden.
 */
export type ToolCallIndex = {
  results: Map<string, ToolCallResultContent>
  /** tool_call parts by call_id (these calls render their results themselves) */
  calls: Map<string, ToolCallContent>
}

export const buildToolCallIndex = (messages: ChatMessage[]): ToolCallIndex => {
  const results = new Map<string, ToolCallResultContent>()
  const calls = new Map<string, ToolCallContent>()
  for (const m of messages) {
    for (const part of m.message.content) {
      if (part.type === 'tool_call' && part.call_id) calls.set(part.call_id, part)
      else if (part.type === 'tool_call_result' && part.call_id) results.set(part.call_id, part)
    }
  }
  return { results, calls }
}

export const ToolCallIndexContext = React.createContext<ToolCallIndex>({ results: new Map(), calls: new Map() })

export const useToolCallIndex = (): ToolCallIndex => React.useContext(ToolCallIndexContext)
