import React from 'react'
import Layout from '@/components/layout/layout.tsx'
import { useRoute } from '@/app-router.tsx'
import AgentView from '@/app/agents/agent.view.tsx'

const AgentPage = () => {
  const { params } = useRoute()
  const name = decodeURIComponent(params?.name || '')

  return (
    <Layout>

      <main className={"absolute top-12 left-0 w-full h-[calc(100vh-4rem)]"}>
        <div className="content mx-auto">
          <div className="flex flex-col gap-4 py-4 md:gap-6 md:py-6 px-4 flex-1">
            <AgentView key={name} name={name} />
          </div>
        </div>
      </main>
    </Layout>
  )
}

export default AgentPage
