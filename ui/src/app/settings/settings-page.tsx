import React from 'react'
import SettingsView from '@/app/settings/settings-view.tsx'
import Header from '@/components/header.tsx'
import Layout from '@/components/layout/layout.tsx'
import { SettingsDialog } from '@/app/settings/components/settings-dialog.tsx'

const SettingsPage = () => {
  return (
    <Layout>
      <div className={"p-4"}>
        <Header title={"Settings"} subtitle={"Configure your application settings"} />
        <SettingsView />
        {/*<SettingsDialog />*/}
      </div>
    </Layout>
  )
}

export default SettingsPage