import React from 'react'
import Layout from '@/components/layout/layout.tsx'
import MainContent from '@/components/layout/main-content.tsx'
import Header from '@/components/header.tsx'
import { Button } from '@/components/ui/button.tsx'

const WizardsPage = () => {
  return (
    <Layout>
      <MainContent>
        <Header title={"Wizards"} subtitle={"Manage your agentic wizards here"}>
          <Button>Create Wizard</Button>
        </Header>
      </MainContent>
    </Layout>
  )
}

export default WizardsPage