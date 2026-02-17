import React from 'react'
import Layout from '@/components/layout/layout.tsx'
import MainContent from '@/components/layout/main-content.tsx'
import Header from '@/components/header.tsx'
import { Button } from '@/components/ui/button.tsx'

const ToolsPage = () => {
  return (
    <Layout>
      <MainContent>
        <Header title={"Tools"} subtitle={"Tools can be used by agentic wizards to perform actions or retrieve information."}>
          {/*<Button>Refresh</Button>*/}
        </Header>
      </MainContent>
    </Layout>
  )
}

export default ToolsPage