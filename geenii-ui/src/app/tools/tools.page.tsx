import React from 'react'
import MainContent from '@/components/layout/main-content.tsx'
import Header from '@/components/header.tsx'
import ToolsView from '@/app/tools/tools.view.tsx'
import ConsoleLayout from '@/components/layout/console-layout.tsx'

const ToolsPage = () => {
  return (
    <ConsoleLayout>
      <MainContent>
        <Header title={"Tool Sandbox"} subtitle={"Tools can be used by agentic wizards to perform actions or retrieve information."}>
          {/*<Button>Refresh</Button>*/}
        </Header>

        <ToolsView />
      </MainContent>
    </ConsoleLayout>
  )
}

export default ToolsPage
