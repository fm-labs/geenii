import React from 'react'
import Layout from '@/components/layout/layout.tsx'
import MainContent from '@/components/layout/main-content.tsx'
import { useRoute } from '@/app-router.tsx'
import AgentView from '@/app/agents/agent.view.tsx'

const AgentPage = () => {
  const { params } = useRoute()
  const name = decodeURIComponent(params?.name || '')

  return (
    <Layout>
      <MainContent>
        <AgentView key={name} name={name} />
      </MainContent>
    </Layout>
  )
}

export default AgentPage
