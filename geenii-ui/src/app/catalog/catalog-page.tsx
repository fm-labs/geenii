import React from 'react'
import ConsoleLayout from '@/components/layout/console-layout.tsx'
import { useRoute } from '@/app-router.tsx'
import { AiModelSettingsView } from '@/app/console/components/ai-model-settings-view.tsx'
import { DockerMcpCatalogView } from '@/app/catalog/docker-mcp-catalog-view.tsx'

const CatalogPage = () => {
  const { params } = useRoute()
  const section = decodeURIComponent(params?.section || '')
  const getSectionContent = (section: string) => {
    switch (section) {
      case 'mcp':
        return <DockerMcpCatalogView />
      case 'models':
        return <AiModelSettingsView />
      default:
        return <div>Section {section} not found</div>
    }
  }

  return (
    <ConsoleLayout>
      <h1>Catalog Page {section}</h1>
      {getSectionContent(section)}
    </ConsoleLayout>
  )
}

export default CatalogPage
