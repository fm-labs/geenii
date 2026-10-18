import ChatContextProvider from './components/ChatContextProvider.tsx'
import CompletionChat from './completion-chat.tsx'
import React from 'react'
import ConsoleLayout from '@/components/layout/console-layout.tsx'

const CompletionChatPage = () => {

  const contextProps = {
    //className: 'CustomChatClass',
    //enableSuggestions: true,
    //suggestions: ['Hello, how can I help you?', 'What is the weather like today?'],
    enableFiles: true,
    files: [],
  }

  return (<ConsoleLayout>
      <ChatContextProvider {...contextProps}>
        <div className="content">
          <div className="flex flex-col justify-center min-h-screen">
            <div className="flex flex-col justify-center">
              <div className={'grow'}>
                <div className="max-w-3xl mx-auto p-4">
                  <CompletionChat enableFiles={false} />
                </div>
              </div>
            </div>
          </div>
        </div>
      </ChatContextProvider>
    </ConsoleLayout>
  )
}

export default CompletionChatPage
