import React from 'react'
import SettingsView from '@/app/settings/settings-view.tsx'
import Header from '@/components/header.tsx'
import Layout from '@/components/layout/layout.tsx'
import { SettingsDialog } from '@/app/settings/components/settings-dialog.tsx'
import MainContent from '@/components/layout/main-content.tsx'

const SettingsPage = () => {
  return (
    <Layout>
      <MainContent>
        <Header title={"Settings"} subtitle={"Configure your application settings"} />
        <SettingsView />
        {/*<SettingsDialog />*/}
      </MainContent>
    </Layout>
  )
}

export default SettingsPage