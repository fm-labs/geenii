/**
 * @deprecated Use ChatMessage with ChatMessageContent instead
 */
export type ChatMessageCompat = {
  role: 'user' | 'assistant' | 'system'
  type: 'text' | 'image'
  content: string
}


export type ChatMessageContent = {
  id?: string
  type: 'text' | 'image' | 'code' | 'function' | 'function_permission' | 'approval' | 'task'
  text?: string
  data?: any
  function?: {
    name: string
    args: any
  },
}

export type FunctionPermissionChatMessageContent = ChatMessageContent & {
  type: 'function_permission'
  text: string // ALLOW, ALLOW_ALWAYS or DENY
  function: {
    name: string
    args: any
  }
}

export type ApprovalChatMessageContent = ChatMessageContent & {
  id: string
  type: 'approval'
  text: string // description of what is being requested
  data: {
    scope: 'REQUEST' | 'RESPONSE'
    requestId?: string // present if scope is RESPONSE
  }
}

export type ChatMessage = {
  //senderId?: string
  role: 'user' | 'assistant' | 'system'
  content: ChatMessageContent[],
}