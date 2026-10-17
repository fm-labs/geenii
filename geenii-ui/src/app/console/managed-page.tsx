import React from 'react'
import ConsoleLayout from '@/components/layout/console-layout.tsx'
import { useRoute } from '@/app-router.tsx'
import { McpServersSettingsView } from '@/app/console/components/mcp-servers-settings-view.tsx'
import Header from '@/components/header.tsx'
import AgentsView from '@/app/agents/agents.view.tsx'

const ManagedPage = () => {
  const { params } = useRoute()
  const section = decodeURIComponent(params?.section || '')

  const getSectionContent = (section: string) => {
    switch (section) {
      case 'agents':
        return <AgentsView />
      case 'mcp-servers':
        return <McpServersSettingsView />
      default:
        return <div>Section {section} not found</div>
    }
  }

  return (
    <ConsoleLayout>
      <Header title={`Managed ${section}`} subtitle={`Manage your ${section} here.`} />
      {getSectionContent(section)}
    </ConsoleLayout>
  )
}

export default ManagedPage
