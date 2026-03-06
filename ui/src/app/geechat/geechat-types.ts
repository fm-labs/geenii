export type ChatMessage = {
  id: string;
  type: 'message'
  room_id: string
  sender_id: string
  content: ContentPart[]
  created_at: number // timestamp in milliseconds
}

type TextContent = {
  type: 'text'
  text: string
}

type ImageContent = {
  type: 'image'
  url: string
  alt?: string
}

type ToolCallContent = {
  type: 'tool_call'
  name: string
  arguments?: any
  call_id?: string
}

type ToolCallResultContent = {
  type: 'tool_call_result'
  name: string
  arguments?: any
  call_id?: string
  result?: any
  error?: string
}

type JsonContent = {
  type: 'json'
  data: any
}

type UserConfirmationContent = {
  type: 'confirmation'
  confirmation_id: string
  text: string
  confirmed: boolean | null
}

export type UserInteractionContent = {
  type: 'interaction'
  interaction_id: string
  interaction_type: string
  text: string
  choices: string[]
  choice: string | null
}


type ContentPart = TextContent | ImageContent | ToolCallContent | ToolCallResultContent |
  JsonContent | UserConfirmationContent | UserInteractionContent
