import React from 'react'
import MainContent from '@/components/layout/main-content.tsx'
import AgentsView from '@/app/agents/agents.view.tsx'
import XchatProvider from '@/app/xchat/xchat-provider.tsx'

const AgentsPage = () => {
  return (
    <XchatProvider>
      <MainContent>
        <AgentsView />
      </MainContent>
    </XchatProvider>
  )
}

export default AgentsPage
