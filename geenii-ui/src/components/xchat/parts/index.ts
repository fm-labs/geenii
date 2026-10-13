import { ContentPartRenderers } from '@/components/xchat/chat.types.ts'
import { AudioPart, EmbedPart, FilePart, ImagePart, JsonPart, TextPart } from './media-parts.tsx'
import {
  ConfirmationPart,
  FunctionCallPart,
  InteractionPart,
  ToolCallPart,
  ToolCallResultPart,
} from './tool-parts.tsx'

export * from './media-parts.tsx'
export * from './tool-parts.tsx'

/** Built-in renderer for every content part type. Override single types via <ChatProvider renderers={…}>. */
export const defaultRenderers: Required<ContentPartRenderers> = {
  text: TextPart,
  image: ImagePart,
  audio: AudioPart,
  file: FilePart,
  embed: EmbedPart,
  json: JsonPart,
  function: FunctionCallPart,
  tool_call: ToolCallPart,
  tool_call_result: ToolCallResultPart,
  interaction: InteractionPart,
  confirmation: ConfirmationPart,
}
