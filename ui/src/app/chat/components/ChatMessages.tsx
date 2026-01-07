import React from 'react'
import { ChatContext } from '@/app/chat/components/ChatContext.tsx'
import { ModelThinkingIndicator } from '@/app/chat/components/ModelThinkingIndicator.tsx'
import TypewriterText from '@/ui/TypewriterText.tsx'
import {
  ApprovalChatMessageContent,
  ChatMessage,
  ChatMessageContent,
  FunctionPermissionChatMessageContent,
} from '@/app/chat/components/chat.types.ts'
import { Button } from '@/components/ui/button.tsx'
import { CHAT_TYPEWRITER_ENABLED } from '@/constants.ts'
import { OutputDataMarkdown } from '@/ui/OutputDataMarkdown.tsx'

const ChatMessageOutputText = ({ text, isLast }: { text: string, isLast?: boolean }) => {
  if (CHAT_TYPEWRITER_ENABLED && isLast) {
    return <div
      className={'output-data'}>
      <TypewriterText text={text.trim()} limit={2500} cursorChar={'_'}>

      </TypewriterText>
    </div>
  }
}

const ChatMessageItem = ({ message, isLast }: { message: ChatMessage, isLast?: boolean }) => {
  const renderContentPart = (part: ChatMessageContent, partIndex: number, isLast: boolean = false) => {
    if (part.type === 'text' && CHAT_TYPEWRITER_ENABLED && isLast) {
      return <div
        className={'output-data'}>
        <TypewriterText text={part?.text?.trim()} limit={2500} cursorChar={'_'}></TypewriterText>
      </div>
    } else if (part.type === 'text') {
      //return <div key={partIndex} className={"whitespace-pre-wrap overflow-x-clip"}>{part?.text?.trim()}</div>
      return <div className={'output-data'}>
        <OutputDataMarkdown data={part?.text?.trim()} />
      </div>
    } else if (part.type === 'code') {
      return <pre key={partIndex} className={"rounded border border-white overflow-x-auto mb-1"}><code>{part?.text?.trim()}</code></pre>
    } else if (part.type === 'image') {
      if (part?.data?.url) {
        return <img key={partIndex} src={part.data.url} alt="Image" className={"max-w-full h-auto"} />
      }
      else if (part?.data?.url) {
        return <img key={partIndex} src={part.data.base64} alt="Image" className={"max-w-full h-auto"} />
      }
    } else if (part.type === 'function') {
      return <div key={partIndex} className={"border border-blue-800 rounded"}>
        <strong>Function Call:</strong> {part.function?.name}({JSON.stringify(part.function?.args)})
      </div>
    } else if (part.type === 'function_permission') {
      const permPart = part as FunctionPermissionChatMessageContent
      return <div key={partIndex} className={"border border-orange-700 rounded"}>
        <strong>Function Permission:</strong> {permPart.function?.name}({JSON.stringify(permPart.function?.args)}) - <em>{permPart.text} ({permPart?.data?.approved ? "Approved" : "Denied"})</em>
      </div>
    } else if (part.type === 'approval' && part.data.scope === 'REQUEST') {
      const approvalPart = part as ApprovalChatMessageContent
      return <div key={partIndex} className={"border border-red-900 rounded"}>
        <strong>Approval ({approvalPart.data.scope}):</strong> {approvalPart.text}
        <Button>Approve</Button>
        <Button>Deny</Button>
      </div>
    } else if (part.type === 'approval' && part.data.scope === 'RESPONSE') {
      const approvalPart = part as ApprovalChatMessageContent
      return <div key={partIndex} className={"border border-red-900 rounded"}>
        <strong>Approval ({approvalPart.data.scope}):</strong> {approvalPart.text}
      </div>
    } else if (part.type === 'task') {
      return <div key={partIndex} className={"text-sm text-muted-foreground"}>
        <strong>Task:</strong> {part.text} - <em>Status: {part.data?.status}</em>
      </div>
    } else {
      return <p key={partIndex}>[Unsupported content type: {part.type}]</p>
    }
  }

  const renderUserContentPart = (part: ChatMessageContent, partIndex: number) => {
    if (part.type === 'text') {
      return <div key={partIndex} className={"whitespace-pre-wrap overflow-x-clip"}>{part?.text?.trim()}</div>
    } else {
      return <p key={partIndex}>[Unsupported content type in user message: {part.type}]</p>
    }
  }

  return message.content.map((msgContent: ChatMessageContent, cidx) => {
    if (message.role === 'user') {
      return (<div className={'Chat-message Chat-message-user'} role={message.role} key={`m-${cidx}`}>
        {renderUserContentPart(msgContent, cidx)}
      </div>)
    }

    return (<div className={`Chat-message Chat-message-${message.role}`} role={message.role} key={`m-${cidx}`}>
      {/*message.role==='user' && msgContent.type==='text'
            ? <div className={'input-data'}>{msgContent.text}</div>
            :<div
              className={'output-data'}>
              <TypewriterText text={msgContent.text} limit={2500} cursorChar={'_'}></TypewriterText>
            </div>*/}
      {renderContentPart(msgContent, cidx, isLast)}
    </div>)
  })
}

const ChatMessages = () => {

  const chatContext = React.useContext(ChatContext)
  if (!chatContext) {
    throw new Error('ChatContext is not provided')
  }
  const { messages, addMessage, modelName, setModelName, isThinking } = chatContext


  const renderMessages = () => {
    return messages.map((message: ChatMessage, idx) => {
      return <ChatMessageItem key={`msg-${idx}`} message={message} />
    })
  }

  return (
    <div className={'Chat-messages'}>
      {renderMessages()}
      <div className={'Chat-model-loading'}><ModelThinkingIndicator show={isThinking} /></div>
    </div>
  )
}

export default ChatMessages