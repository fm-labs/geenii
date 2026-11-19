import React from 'react'
import MainLayout from '@/components/layout/main-layout.tsx'
import LauncherView from '@/app/launcher/launcher.view.tsx'
import { useRoute } from '@/app-router.tsx'

const LauncherPage = () => {
  const { params } = useRoute()
  const tabId = params?.tabId || 'agents'

  return (
    <MainLayout>
      <main className={"absolute top-12 left-0 w-full h-[calc(100vh-4rem)]"}>
        <LauncherView tabId={tabId} />
      </main>
    </MainLayout>
  )
}

export default LauncherPage
