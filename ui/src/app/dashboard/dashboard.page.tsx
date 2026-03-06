import React, { PropsWithChildren } from 'react'
import Layout from '@/components/layout/layout.tsx'
import AgentsView from '@/app/agents/agents.view.tsx'
import ToolsView from '@/app/tools/tools.view.tsx'
import AppsView from '@/app/apps/apps-view.tsx'
import { cn } from '@/lib/utils.ts'


const DashboardCard = ({ title, description, children }: PropsWithChildren<{ title: string, description: string }>) => {
  return (
    <div className={'dashboard-card rounded-lg border p-4'}>
      <h3 className={'font-bold text-lg'}>{title}</h3>
      <p>{description}</p>
      <div>{children}</div>
    </div>
  )
}

const DashboardHeader = ({ title }: { title: string }) => {
  return (
    <div className={'dashboard-header mb-6'}>
      <h1 className={'text-2xl font-bold'}>{title}</h1>
      <p className={'text-gray-600'}>Get an overview of your XAI system and access key features.</p>
    </div>
  )
}

const DashboardSection = ({ title, className, children }: PropsWithChildren<{ title: string, className?: string }>) => {
  return (
    <div className={cn('dashboard-section p-20 min-h-screen border-b-13', className)}>
      <div className={'p-12 text-center'}>
        <h2 className={'text-xl font-semibold text-center'}>{title}</h2>
      </div>
      <div>{children}</div>
    </div>
  )
}

const DashboardPage = () => {
  return (
    <Layout>
      <div className={'pt-10'}>

        <DashboardSection title={"Your Agents"}>
          <a href={'#/agents'} className={'text-sm mb-4 inline-block'}>Manage Agents</a>
          <AgentsView />
        </DashboardSection>

        <DashboardSection title={"Your Apps"} className={''}>
          <AppsView />
        </DashboardSection>

        <DashboardSection title={"Your Tools"}>
          <ToolsView />
        </DashboardSection>
      </div>
    </Layout>
  )
}

export default DashboardPage