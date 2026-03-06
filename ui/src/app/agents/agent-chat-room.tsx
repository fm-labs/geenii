import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import AssistantChatInputForm from '@/app/assistants/assistant-chat-input-form.tsx'
import { ContentPart } from '@/app/geechat/geechat-contents.tsx'
import { GeeChatContext, GeeChatContextProvider } from '@/app/geechat/geechat-context.tsx'
import React, { useCallback } from 'react'
import { XAI_API_URL } from '@/constants.ts'

function ChatMessageItem({ message }) {
  const { username } = React.useContext(GeeChatContext)
  const isUser = message.sender_id === username || message.sender_id === 'tool'

  return (
    <div className={`flex gap-2.5 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
      <Avatar className="w-7 h-7 flex-shrink-0 mt-0.5">
        <AvatarFallback className={`text-[10px] font-mono ${
          isUser ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground'
        }`}>
          {isUser ? 'U' : 'AI'}
        </AvatarFallback>
      </Avatar>

      <div className={`flex flex-col gap-1.5 max-w-[calc(100%-36px)] ${isUser ? 'items-end' : 'items-start'}`}>
        <span className="text-[10px] text-muted-foreground px-1">
          {isUser ? 'User' : 'Assistant'}
        </span>
        {message.content.map((part, idx) => (
          <ContentPart key={idx} part={part} isUser={isUser} />
        ))}
      </div>
    </div>
  )
}

// ─── Root ─────────────────────────────────────────────────────────────────────

export default function AgentChatRoom() {
  const context = React.useContext(GeeChatContext)
  if (!context) {
    throw new Error("GeeChatContext not found. Make sure to wrap AgentChatRoom with GeeChatContextProvider.")
  }

  const { roomId, username, messages } = context
  const scrollAreaRef = React.useRef(null)
  const bottomRef = React.useRef(null)


  const handleInputFormSubmit = useCallback(async (input) => {
    console.log("User input submitted:", input)
    // Here you would typically send the input to your backend or agent system
    // For this example, we'll just log it and add a dummy response

    // Add user message to context (this would normally be done after confirming the message was sent successfully)
    // context.addMessage({
    //   type: 'message',
    //   room_id: roomId,
    //   sender_id: username,
    //   content: [{ type: 'text', text: input }],
    // })

    // Simulate assistant response
    // setTimeout(() => {
    //   context.addMessage({
    //     type: 'message',
    //     room_id: roomId,
    //     sender_id: 'assistant1',
    //     content: [{ type: 'text', text: `You said: ${input}` }],
    //   })
    // }, 3000)

    const sendMessage = async () => {
      try {
        const response = await fetch(XAI_API_URL + `api/v1/chat/rooms/${roomId}/messages`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            room_id: roomId,
            sender_id: username,
            content: [{ type: 'text', text: input }],
          }),
        })

        if (!response.ok) {
          throw new Error(`Failed to send message: ${response.statusText}`)
        }

        const data = await response.json()
        console.log("Message sent successfully:", data)
        return data
      } catch (error) {
        console.error("Error sending message:", error)
      }
    }

    const response = await sendMessage()
    if (response) {
      console.log("Server response for sent message:", response)
      //context.addMessage(response)
    }
  }, [context, roomId, username])

  // React.useEffect(() => {
  //   const fetchMessages = async () => {
  //     try {
  //       const response = await fetch(XAI_API_URL + `api/v1/chat/rooms/${roomId}/messages`)
  //       if (response.ok) {
  //         const data = await response.json()
  //         console.log('Fetched messages:', data)
  //         context.setMessages(data || [])
  //       } else {
  //         console.error('Failed to fetch messages:', response.statusText)
  //       }
  //     } catch (error) {
  //       console.error('Error fetching messages:', error)
  //     }
  //   }
  //   fetchMessages()
  // })

  // React.useEffect(() => {
  //   // Scroll to bottom whenever messages change
  //   if (scrollAreaRef.current) {
  //     console.log('scrollArea:', scrollAreaRef.current)
  //     setTimeout(() => {
  //       scrollAreaRef.current.scrollTo({
  //         top: scrollAreaRef.current.scrollHeight,
  //         behavior: 'smooth',
  //       })
  //     }, 1000) // delay to ensure messages are rendered
  //   }
  // }, [messages])

  React.useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages]) // replace [] with [messages] if messages is a state variable

  if (!context) {
    return (
      <div className="flex items-center justify-center h-screen">
        <span className="text-muted-foreground">Not in chat context...</span>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-screen max-w-2xl mx-auto bg-background">
      {/*<header className="sticky top-0 z-10 flex items-center gap-2 px-4 py-2.5 border-b bg-background/90 backdrop-blur-sm">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
        <h1 className="text-xs text-muted-foreground">Agent Chat Room</h1>
        <Badge variant="outline" className="ml-auto font-mono text-[10px] text-muted-foreground h-5">
          #{EXAMPLE_MESSAGES[0].room_id}
        </Badge>
      </header>*/}

      <ScrollArea className="flex-1 mb-6" ref={scrollAreaRef}>
        <div className="flex flex-col gap-5 px-4 py-5">
          {/*<div className="flex items-center gap-3">
            <Separator className="flex-1" />
            <span className="text-[10px] font-mono text-muted-foreground shrink-0">Today · 14:32</span>
            <Separator className="flex-1" />
          </div>*/}

          {messages?.map((msg, idx) => (
            <ChatMessageItem key={idx} message={msg} />
          ))}

          <div ref={bottomRef} />  {/* ← anchor at the very bottom */}
        </div>
      </ScrollArea>

      <footer className={'sticky bottom-0 z-10 border-t bg-background/90 backdrop-blur-sm p-4 bg-yellow-500'}>
        <AssistantChatInputForm onSubmit={handleInputFormSubmit} />
      </footer>
    </div>
  )
}