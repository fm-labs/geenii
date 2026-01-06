import ChatContextProvider from './components/ChatContextProvider.tsx'
import CompletionChat from './completion-chat.tsx'
import React from 'react'
import Layout from '../../components/layout/layout.tsx'


// interface ChatAppProps {
//     className?: string;
//     enableSuggestions?: boolean;
//     suggestions?: string[];
//     enableFiles?: boolean;
//     //files?: File[];
// }

const CompletionChatPage = () => {

  const contextProps = {
    //className: 'CustomChatClass',
    //enableSuggestions: true,
    //suggestions: ['Hello, how can I help you?', 'What is the weather like today?'],
    //enableFiles: true,
    //files: [],
  }

  return (<Layout>
      <ChatContextProvider {...contextProps}>
        <div className="max-w-screen-md mx-auto p-4">
          <CompletionChat />
        </div>
      </ChatContextProvider>
    </Layout>
  )
}

export default CompletionChatPage
