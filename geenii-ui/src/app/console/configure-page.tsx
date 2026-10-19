import React from 'react'
import ConsoleLayout from '@/components/layout/console-layout.tsx'
import { useRoute } from '@/app-router.tsx'
import { McpServersSettingsView } from '@/app/console/components/mcp-servers-settings-view.tsx'
import { AgentsSettingsView } from '@/app/console/components/agents-settings-view.tsx'
import { SkillsSettingsView } from '@/app/console/components/skills-settings-view.tsx'
import Header from '@/components/header.tsx'

const ConfigurePage = () => {
  const { params } = useRoute()
  const section = decodeURIComponent(params?.section || '')

  const getSectionContent = (section: string) => {
    switch (section) {
      case 'agents':
        return <AgentsSettingsView />
      case 'skills':
        return <SkillsSettingsView />
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

export default ConfigurePage
