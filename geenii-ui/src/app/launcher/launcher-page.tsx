import React from 'react'
import MainLayout from '@/components/layout/main-layout.tsx'
import MainContent from '@/components/layout/main-content.tsx'
import LauncherView from '@/app/launcher/launcher.view.tsx'

const LauncherPage = ({ tabId }: { tabId?: string }) => {
  return (
    <MainLayout>
      <MainContent>
        <LauncherView tabId={tabId} />
      </MainContent>
    </MainLayout>
  )
}

export default LauncherPage
