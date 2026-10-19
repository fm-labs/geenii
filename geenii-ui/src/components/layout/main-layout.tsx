import React, { PropsWithChildren } from 'react'
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"
import { Separator } from "@/components/ui/separator"
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { AppSidebar } from '@/components/layout/app-sidebar.tsx'

const MainLayout = (props: PropsWithChildren<{
  /** Rendered at the top of the sidebar, above the chat list */
  sidebarHeader?: React.ReactNode
}>) => {

  return (
    <SidebarProvider
      style={
        {
          "--sidebar-width": "350px",
        } as React.CSSProperties
      }
      defaultOpen={false}
    >
      <AppSidebar sidebarHeader={props.sidebarHeader} />
      <SidebarInset>
        {/*<header className="sticky top-0 flex shrink-0 items-center gap-2 border-b bg-background p-4">*/}
        {/*  <SidebarTrigger className="-ml-1" />*/}
        {/*  <Separator*/}
        {/*    orientation="vertical"*/}
        {/*    className="mr-2 data-[orientation=vertical]:h-4"*/}
        {/*  />*/}
        {/*  <Breadcrumb>*/}
        {/*    <BreadcrumbList>*/}
        {/*      <BreadcrumbItem className="hidden md:block">*/}
        {/*        <BreadcrumbLink href="#/">Geenii</BreadcrumbLink>*/}
        {/*      </BreadcrumbItem>*/}
        {/*    </BreadcrumbList>*/}
        {/*  </Breadcrumb>*/}
        {/*</header>*/}
        {/*<div className="flex flex-1 flex-col gap-4 p-4">*/}
        {/*  {Array.from({ length: 24 }).map((_, index) => (*/}
        {/*    <div*/}
        {/*      key={index}*/}
        {/*      className="aspect-video h-12 w-full rounded-lg bg-muted/50"*/}
        {/*    />*/}
        {/*  ))}*/}
        {/*</div>*/}
        {props.children}
      </SidebarInset>
    </SidebarProvider>
  )
}

export default MainLayout
