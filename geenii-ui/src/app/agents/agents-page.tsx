import React from 'react'
import Layout from '@/components/layout/layout.tsx'
import MainContent from '@/components/layout/main-content.tsx'
import AgentsView from '@/app/agents/agents.view.tsx'

const AgentsPage = () => {
  return (
    <Layout>
      <MainContent>
        <AgentsView />
      </MainContent>
    </Layout>
  )
}

export default AgentsPage
