import React from 'react'
import Header from '@/components/header.tsx'
import Layout from '@/components/layout/layout.tsx'
import MainContent from '@/components/layout/main-content.tsx'
import AppsView from '@/app/apps/apps-view.tsx'

const AppsPage = () => {
  return (
    <Layout>
      <MainContent>
        <Header title={"Apps"} />
        <AppsView />
      </MainContent>
    </Layout>
  )
}

export default AppsPage