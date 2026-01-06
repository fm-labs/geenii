import React from 'react'
import SettingsView from '@/app/settings/SettingsView.tsx'
import Header from '@/components/header.tsx'
import Layout from '@/components/layout/layout.tsx'

const SettingsPage = () => {
  return (
    <Layout>
      <div className={"max-w-4xl mx-auto bg-accent p-4 rounded-lg"}>
        <Header title={"Settings"} subtitle={"Configure your application settings"} />
        <SettingsView />
      </div>
    </Layout>
  )
}

export default SettingsPage