import React from 'react'
import MainLayout from '@/components/layout/main-layout.tsx'
import MainContent from '@/components/layout/main-content.tsx'
import LauncherView from '@/app/launcher/launcher.view.tsx'

const LauncherPage = () => {
  return (
    <MainLayout>
      <MainContent>
        <LauncherView />
      </MainContent>
    </MainLayout>
  )
}

export default LauncherPage
