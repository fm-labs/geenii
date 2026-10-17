import React from 'react'
import Header from '@/components/header.tsx'
import ConsoleLayout from '@/components/layout/console-layout.tsx'

const ConsolePage = () => {
  return (
    <ConsoleLayout>
      <Header title="Console" subtitle="Welcome to the console page" />
      <p>This is the console page content.</p>
    </ConsoleLayout>
  )
}

export default ConsolePage
