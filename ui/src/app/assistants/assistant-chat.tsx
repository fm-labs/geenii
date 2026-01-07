import React, { useState } from 'react'
import { cn } from '@/lib/utils.ts'
import { Button } from '@/components/ui/button.tsx'
import { ArrowLeft, ImagePlus, MoreVertical, Paperclip, Phone, Plus, Send, Video } from 'lucide-react'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar.tsx'
import { Fragment } from 'react/jsx-runtime'
import { format } from 'date-fns'
import type { ChatUser, Convo } from '@/app/assistants/chat-types.ts'
import { ChatMessage } from '@/app/chat/components/chat.types.ts'
import ChatMessages from '@/app/chat/components/ChatMessages.tsx'
import { ChatContext } from '@/app/chat/components/ChatContext.tsx'
import AssistantChatInputForm from '@/app/assistants/assistant-chat-input-form.tsx'
import { AppContext } from '@/context/AppContext.tsx'
import useNotification from '@/hooks/useNotification.ts'
import { XAI_API_URL } from '@/constants.ts'

interface AssistantChatProps {
  assistant: Assistant,
  conversationId?: string | null,
}

const AssistantChat = ({ assistant, conversationId: initialConvId }: AssistantChatProps) => {

  const appContext = React.useContext(AppContext)
  if (!appContext) {
    throw new Error('AppContext is not provided')
  }

  const chatContext = React.useContext(ChatContext)
  if (!chatContext) {
    throw new Error('ChatContext is not provided')
  }
  const { addMessage, messages, isThinking, setIsThinking } = chatContext
  const notify = useNotification()

  const [conversationId, setConversationId] = useState<string | null>(initialConvId)

  // const currentMessage = messages.reduce(
  //   (acc: Record<string, ChatMessage[]>, obj: ChatMessage) => {
  //     //const key = format(obj.timestamp, 'd MMM, yyyy')
  //     const key = "default"
  //
  //     // Create an array for the category if it doesn't exist
  //     if (!acc[key]) {
  //       acc[key] = []
  //     }
  //
  //     // Push the current object to the array
  //     acc[key].push(obj)
  //
  //     return acc
  //   },
  //   {}
  // )

  const [mobileSelectedUser, setMobileSelectedUser] = useState<ChatUser | null>(
    null,
  )

  const addUserMessage = React.useCallback((content: string) => {
    const message: ChatMessage = { role: 'user', content: [{type: 'text', text: content}] }
    addMessage(message)
  }, [])

  const addAssistantMessage = React.useCallback((content: string) => {
    const message: ChatMessage = { role: 'assistant', content: [{type: 'text', text: content}] }
    addMessage(message)
  }, [])

  const postUserMessage = async (input: string): Promise<ChatMessage[]> => {

    setIsThinking(true)
    try {
      let submitUrl = XAI_API_URL + `ai/v1/assistants/${assistant.id}/chats`
      if (conversationId) {
        submitUrl += `/${conversationId}`
      }

      const responseRaw = await fetch(submitUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          input: input,
          model: assistant.model,
          //tools: assistant.tools,
        }),
      })
      const response = await responseRaw.json()
      console.log('>> AI AGENT CHAT SUBMISSION RESPONSE DATA', response)

      // check for error message in response
      if (response && response?.error) {
        console.error('>> ERROR IN XAI RESPONSE', response.error)
        notify.error('Error generating response: ' + response.error)
        throw new Error(response.error)
      }

      if (response && !conversationId && response?.id) {
        console.log('>> SETTING NEW CONVERSATION ID FROM RESPONSE:', response.id)
        setConversationId(response.id)
      }

      if (!response?.messages) {
        console.warn('>> NO MESSAGES IN XAI RESPONSE')
        return []
      }

      // if (!response || !response.output || response.output.length===0) {
      //   console.warn('>> NO OUTPUT FROM XAI RESPONSE')
      //   return ''
      // }
      // return response.output[0]?.content[0]?.text || 'ERROR: No content in response'
      return response.messages;
    } catch (e) {
      console.error(e)
    } finally {
      setIsThinking(false)
    }

  }


  const submitInput = async (input: string) => {
    console.log('>> SUBMIT INPUT', input)
    if (input.trim()==='') {
      console.warn('>> EMPTY INPUT, NOT SUBMITTING')
      return
    }

    addUserMessage(input)
    setIsThinking(true)

    const messages = await postUserMessage(input.trim())
    messages.forEach(message => {
      addMessage(message)
    })
  }

  React.useEffect(() => {
    if (initialConvId) {
      console.log('Setting initial conversation ID:', initialConvId)
      setConversationId(initialConvId)
    }
  }, [initialConvId])

  return (
    <div
      className={cn(
        'bg-background absolute inset-0 start-full z-50 hidden w-full max-w-4xl flex-1 flex-col border shadow-xs sm:static sm:z-auto sm:flex sm:rounded-md',
        mobileSelectedUser && 'start-0 flex',
      )}
    >
      {/* Top Part */}
      <div className="bg-card mb-1 flex flex-none justify-between p-4 shadow-lg sm:rounded-t-md">
        {/* Left */}
        <div className="flex gap-3">
          <Button
            size="icon"
            variant="ghost"
            className="-ms-2 h-full sm:hidden"
            onClick={() => setMobileSelectedUser(null)}
          >
            <ArrowLeft className="rtl:rotate-180" />
          </Button>
          <div className="flex items-center gap-2 lg:gap-4">
            <Avatar className="size-9 lg:size-11">
              <AvatarImage
                src={assistant?.imageUrl}
                alt={assistant?.name}
              />
              <AvatarFallback>{assistant.name}</AvatarFallback>
            </Avatar>
            <div>
              <span className="col-start-2 row-span-2 text-sm font-medium lg:text-base">
                {assistant.name}
              </span>
              <span
                className="text-muted-foreground col-start-2 row-span-2 row-start-2 line-clamp-1 block max-w-32 text-xs text-nowrap text-ellipsis lg:max-w-none lg:text-sm">
                {assistant.description}{' '}
                {`${assistant?.tools?.length} Tools available`}
              </span>
            </div>
          </div>
        </div>

        {/* Right */}
        <div className="-me-1 flex items-center gap-1 lg:gap-2">
          {/*<Button
            size="icon"
            variant="ghost"
            className="hidden size-8 rounded-full sm:inline-flex lg:size-10"
          >
            <Video size={22} className="stroke-muted-foreground" />
          </Button>*/}
          {/*<Button
            size="icon"
            variant="ghost"
            className="hidden size-8 rounded-full sm:inline-flex lg:size-10"
          >
            <Phone size={22} className="stroke-muted-foreground" />
          </Button>*/}
          <Button
            size="icon"
            variant="ghost"
            className="h-10 rounded-md sm:h-8 sm:w-4 lg:h-10 lg:w-6"
          >
            <MoreVertical className="stroke-muted-foreground sm:size-5" />
          </Button>
        </div>
      </div>

      {/* Conversation */}
      <div className="flex flex-1 flex-col gap-2 rounded-md px-4 pt-0 pb-4">
        <div className="flex size-full flex-1">
          <div className="chat-text-container relative -me-4 flex flex-1 flex-col overflow-y-hidden">
            <div
              className="chat-flex flex h-40 w-full grow flex-col-reverse justify-start gap-4 overflow-y-auto py-2 pe-4 pb-4">
              {/*currentMessage &&
                Object.keys(currentMessage).map((key) => (
                  <Fragment key={key}>
                    {currentMessage[key].map((msg, index) => (
                      <div
                        key={`${msg.sender}-${msg.timestamp}-${index}`}
                        className={cn(
                          'chat-box max-w-72 px-3 py-2 break-words shadow-lg',
                          msg.sender === 'You'
                            ? 'bg-primary/90 text-primary-foreground/75 self-end rounded-[16px_16px_0_16px]'
                            : 'bg-muted self-start rounded-[16px_16px_16px_0]'
                        )}
                      >
                        {msg.message}{' '}
                        <span
                          className={cn(
                            'text-foreground/75 mt-1 block text-xs font-light italic',
                            msg.sender === 'You' &&
                            'text-primary-foreground/85 text-end'
                          )}
                        >
                                  {format(msg.timestamp, 'h:mm a')}
                                </span>
                      </div>
                    ))}
                    <div className='text-center text-xs'>{key}</div>
                  </Fragment>
                ))*/}
              <div className={'Chat'}>
                <div className={'Chat-body'}>
                  <ChatMessages />
                </div>
              </div>
            </div>
          </div>
        </div>

        <AssistantChatInputForm onSubmit={submitInput} />

      </div>
    </div>
  )
}

export default AssistantChat