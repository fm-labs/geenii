import React from 'react'
import Header from '@/components/header.tsx'
import MainLayout from '@/components/layout/main-layout.tsx'
import MainContent from '@/components/layout/main-content.tsx'
import AppsView from '@/app/apps/apps-view.tsx'

const AppsPage = () => {
  return (
    <MainLayout>
      <MainContent>
        <Header title={"Apps"} />
        <AppsView />
      </MainContent>
    </MainLayout>
  )
}

export default AppsPage
