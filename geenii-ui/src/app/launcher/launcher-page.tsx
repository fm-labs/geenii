import React from 'react'
import LauncherView from '@/app/launcher/launcher.view.tsx'
import LauncherLayout from '@/app/launcher/launcher-layout.tsx'
import LauncherHeader from '@/app/launcher/launcher-header.tsx'

const LauncherPage = () => {

  const searchParams = new URLSearchParams(window.location.search)
  const tabParam = searchParams.get('tab')
  console.log(window.location)

  return (
    <LauncherLayout>
      <LauncherHeader />
      <main className={"absolute top-12 left-0 w-full h-[calc(100vh-4rem)]"}>
        <LauncherView />
      </main>
    </LauncherLayout>
  )
}

export default LauncherPage
