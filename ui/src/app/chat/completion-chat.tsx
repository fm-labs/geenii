import React from 'react'
import ChatFiles from './components/ChatFiles.tsx'
import { AppContext } from '../../context/AppContext.tsx'
import { ChatContext } from './components/ChatContext.tsx'
import { ChatMessage } from './components/chat.types.ts'
import ChatPromptSuggestions from '@/app/chat/components/ChatPromptSuggestions.tsx'
import ChatMessages from '@/app/chat/components/ChatMessages.tsx'
import ChatInput from '@/app/chat/components/ChatInput.tsx'
import ChatModelSelector from '@/app/chat/components/ChatModelSelector.tsx'
import useNotification from '../../hooks/useNotification.ts'
import './Chat.scss'


interface ChatProps {
  className?: string;
  slashCommands?: string[];
  enableFiles?: boolean;
  files?: File[];
  enableSuggestions?: boolean;
  suggestions?: string[];
  //enableTools?: boolean;
  //tools?: string[];
  //onSlashCommand?: (command: string) => void;
}

const CompletionChat = (props: ChatProps) => {
  const appContext = React.useContext(AppContext)
  if (!appContext) {
    throw new Error('AppContext is not provided')
  }
  const chatContext = React.useContext(ChatContext)
  if (!chatContext) {
    throw new Error('ChatContext is not provided')
  }
  const { addMessage, modelName, setIsThinking } = chatContext

  const notify = useNotification()

  // const handleAudioRecorded = (audioBlob: Blob) => {
  //   console.log('>> AUDIO RECORDED', audioBlob)
  //   // generate base64 string from audio blob
  //   const reader = new FileReader()
  //   reader.onloadend = () => {
  //     const base64Audio = reader.result as string
  //     console.log('>> BASE64 AUDIO', base64Audio)
  //   }
  // }

  const addUserMessage = (content: string) => {
    const message: ChatMessage = { role: 'user', content: [{type: 'text', text: content}] }
    addMessage(message)
  }

  const addAssistantMessage = (content: string) => {
    const message: ChatMessage = { role: 'assistant', content: [{type: 'text', text: content}] }
    addMessage(message)
  }

  const generateCompletion = async (input: string): Promise<string> => {
    const response = await appContext.xaiApi.generateCompletion({ model: modelName, prompt: input})
      .catch((err) => {
        console.error('Error generating response:', err)
        setIsThinking(false)
        return null
      })
      .finally(() => {
        setIsThinking(false)
      })
    console.log('>> AI COMPLETION RESPONSE', response)

    // check for error message in response
    if (response && response.error) {
      console.error('>> ERROR IN XAI RESPONSE', response.error)
      notify.error('Error generating response: ' + response.error)
    }

    if (!response || !response.output || response.output.length===0) {
      console.warn('>> NO OUTPUT FROM XAI RESPONSE')
      return ''
    }
    return response.output[0]?.content[0]?.text || 'ERROR: No content in response'
  }


  const submitInput = async (input: string) => {
    console.log('>> SUBMIT INPUT', input)
    if (input.trim()==='') {
      console.warn('>> EMPTY INPUT, NOT SUBMITTING')
      return
    }

    // SLASH COMMAND HANDLING
    if (input.startsWith('/')) {
      console.log('>> SLASH COMMAND', input)
      const messageContent = `COMMAND: ${input}`
      addUserMessage(messageContent)

      if (chatContext.commandHandler) {
        await chatContext.commandHandler(input)
          .catch((err) => notify.error(err?.message || 'Error handling slash command'))
      } else {
        console.warn('>> NO ON_SLASH_COMMAND HANDLER PROVIDED')
        //notify.error("No handler for slash command: " + command);
        addAssistantMessage(`Sry, can't handle commands :/`)
      }
      return
    }

    addUserMessage(input)
    setIsThinking(true)

    const responseText = await generateCompletion(input.trim())
    addAssistantMessage(responseText)
  }


  return (
    <div className={props?.className}>
      <div className={'Chat'}>
        <div className={'Chat-body'}>
          <ChatMessages />
          <ChatModelSelector />
          <ChatInput onSubmit={submitInput} />

          {props?.enableFiles && <ChatFiles />}
          {props?.enableSuggestions && <ChatPromptSuggestions />}
        </div>
      </div>
    </div>
  )
}

export default CompletionChat
