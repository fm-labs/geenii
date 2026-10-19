import React from 'react'
import ConsoleLayout from '@/components/layout/console-layout.tsx'
import { useRoute } from '@/app-router.tsx'
import Header from '@/components/header.tsx'
import SystemInfoView from '@/app/console/components/system-info-view.tsx'
import SettingsView from '@/app/console/settings-view.tsx'
import UsageStatsView from '@/app/console/components/usage-stats-view.tsx'

const SystemPage = () => {
  const { params } = useRoute()
  const section = decodeURIComponent(params?.section || '')

  const getSectionContent = (section: string) => {
    switch (section) {
      case 'info':
        return <SystemInfoView />
      case 'settings':
        return <SettingsView />
      case 'stats':
        return <UsageStatsView />
      default:
        return <div>Section {section} not found</div>
    }
  }

  return (
    <ConsoleLayout>
      <Header title={`System ${section}`} />
      {getSectionContent(section)}
    </ConsoleLayout>
  )
}

export default SystemPage
