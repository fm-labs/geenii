import React from 'react'
import { useRoute } from '@/app-router.tsx'
import AgentView from '@/app/agents/agent.view.tsx'

import { ChatProvider, createAgentBackend, createEchoBackend, useChat } from '@/components/xchat'
import useNotification from '@/hooks/useNotification.ts'
import { useApi } from '@/context/api-context.tsx'


const AgentPage = () => {
  const { params } = useRoute()
  const name = decodeURIComponent(params?.name || '')
  const contextId = decodeURIComponent(params?.contextId || '')
  const notify = useNotification()
  const { apiBaseUrl } = useApi()

  const backend = React.useMemo(() => {
    if (!apiBaseUrl || !name) return
    return createAgentBackend({ baseUrl: apiBaseUrl, agent: name })
  }, [name, apiBaseUrl])

  return (
    <ChatProvider backend={backend} contextId={contextId} onError={(error) => notify.error(error)}>
      <AgentView key={name} name={name} contextId={contextId} />
    </ChatProvider>
  )

  // return (
  //   <XchatProvider defaultBackend={name}>
  //
  //     {/*<header className="sticky top-0 flex shrink-0 items-center gap-2 border-b bg-background p-4">*/}
  //     {/*  <SidebarTrigger className="-ml-1" />*/}
  //     {/*  <Separator*/}
  //     {/*    orientation="vertical"*/}
  //     {/*    className="mr-2 data-[orientation=vertical]:h-4"*/}
  //     {/*  />*/}
  //     {/*  <Breadcrumb>*/}
  //     {/*    <BreadcrumbList>*/}
  //     {/*      <BreadcrumbItem className="hidden md:block">*/}
  //     {/*        <BreadcrumbLink href="#/">Geenii</BreadcrumbLink>*/}
  //     {/*      </BreadcrumbItem>*/}
  //     {/*    </BreadcrumbList>*/}
  //     {/*  </Breadcrumb>*/}
  //     {/*</header>*/}
  //
  //     <main className={"absolute left-0 w-full h-[calc(100vh-4rem)]"}>
  //       <div className="content mx-auto">
  //         <div className="flex flex-col py-4 px-4 flex-1">
  //           <AgentView key={name} name={name} contextId={contextId} />
  //         </div>
  //       </div>
  //     </main>
  //   </XchatProvider>
  // )
}

export default AgentPage
