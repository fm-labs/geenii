import React from 'react'
import { useRoute } from '@/app-router.tsx'
import AgentView from '@/app/agents/agent.view.tsx'
import XchatProvider from '@/app/xchat/xchat-provider.tsx'
import { SidebarTrigger } from '@/components/ui/sidebar.tsx'
import { Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList } from '@/components/ui/breadcrumb.tsx'
import { Separator } from '@/components/ui/separator.tsx'

const AgentPage = () => {
  const { params } = useRoute()
  const name = decodeURIComponent(params?.name || '')

  return (
    <XchatProvider>

      <header className="sticky top-0 flex shrink-0 items-center gap-2 border-b bg-background p-4">
        <SidebarTrigger className="-ml-1" />
        <Separator
          orientation="vertical"
          className="mr-2 data-[orientation=vertical]:h-4"
        />
        <Breadcrumb>
          <BreadcrumbList>
            <BreadcrumbItem className="hidden md:block">
              <BreadcrumbLink href="#/">Geenii</BreadcrumbLink>
            </BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>
      </header>

      <main className={"absolute top-14 left-0 w-full h-[calc(100vh-4rem)]"}>
        <div className="content mx-auto">
          <div className="flex flex-col py-4 px-4 flex-1">
            <AgentView key={name} name={name} />
          </div>
        </div>
      </main>
    </XchatProvider>
  )
}

export default AgentPage
