import React from 'react'
import MainLayout from '@/components/layout/main-layout.tsx'
import MainContent from '@/components/layout/main-content.tsx'
import LauncherView from '@/app/launcher/launcher.view.tsx'
import { useRoute } from '@/app-router.tsx'

const LauncherPage = () => {
  const { params } = useRoute()
  const tabId = params?.tabId || 'agents'

  return (
    <MainLayout>
      <MainContent>
        <LauncherView tabId={tabId} />
      </MainContent>
    </MainLayout>
  )
}

export default LauncherPage
