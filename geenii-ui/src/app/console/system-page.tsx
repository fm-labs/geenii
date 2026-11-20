import React from 'react'
import ConsoleLayout from '@/components/layout/console-layout.tsx'
import { useRoute } from '@/app-router.tsx'
import Header from '@/components/header.tsx'
import SystemInfoView from '@/app/console/components/system-info-view.tsx'
import UserSettingsView from '@/app/console/user-settings-view.tsx'
import UsageStatsView from '@/app/console/components/usage-stats-view.tsx'
import SchedulerConfigView from '@/app/console/components/scheduler-config-view.tsx'
import ProcessManagerView from '@/app/console/components/process-manager-view.tsx'
import SupervisorConfigView from '@/app/console/components/supervisor-config-view.tsx'
import ProcessStatsView from '@/app/console/components/process-stats-view.tsx'

const SystemPage = () => {
  const { params } = useRoute()
  const section = decodeURIComponent(params?.section || '')

  const getSectionContent = (section: string) => {
    switch (section) {
      case 'info':
        return <SystemInfoView />
      case 'settings':
        return <UserSettingsView />
      case 'stats':
        return <UsageStatsView />
      case 'process-stats':
        return <ProcessStatsView />
      case 'scheduler':
        return <SchedulerConfigView />
      case 'services':
        return <SupervisorConfigView />
      case 'processes':
        return <ProcessManagerView />
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
