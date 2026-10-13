import { XchatSidebar } from "@/components/layout/xchat-sidebar"
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
import React from 'react'

export default function XchatLayout(props: React.PropsWithChildren<{
  /** Rendered at the top of the sidebar, above the chat list */
  sidebarHeader?: React.ReactNode
}>) {
  return (
    <SidebarProvider>
      <XchatSidebar header={props.sidebarHeader} />
      <SidebarInset>
        {/*<header className="flex h-16 shrink-0 items-center gap-2 border-b px-4">*/}
        {/*  <SidebarTrigger className="-ml-1" />*/}
        {/*  <Separator*/}
        {/*    orientation="vertical"*/}
        {/*    className="mr-2 data-[orientation=vertical]:h-4"*/}
        {/*  />*/}
        {/*  <Breadcrumb>*/}
        {/*    <BreadcrumbList>*/}
        {/*      <BreadcrumbItem className="hidden md:block">*/}
        {/*        <BreadcrumbLink href="#">Xchat</BreadcrumbLink>*/}
        {/*      </BreadcrumbItem>*/}
        {/*      <BreadcrumbSeparator className="hidden md:block" />*/}
        {/*      <BreadcrumbItem>*/}
        {/*        <BreadcrumbPage>Context Topic here</BreadcrumbPage>*/}
        {/*      </BreadcrumbItem>*/}
        {/*    </BreadcrumbList>*/}
        {/*  </Breadcrumb>*/}
        {/*</header>*/}
        {/*<div className="flex flex-1 flex-col gap-4 p-4">*/}
        {/*  <div className="grid auto-rows-min gap-4 md:grid-cols-3">*/}
        {/*    <div className="aspect-video rounded-xl bg-muted/50" />*/}
        {/*    <div className="aspect-video rounded-xl bg-muted/50" />*/}
        {/*    <div className="aspect-video rounded-xl bg-muted/50" />*/}
        {/*  </div>*/}
        {/*  <div className="min-h-[100vh] flex-1 rounded-xl bg-muted/50 md:min-h-min">*/}
        {/*    {props?.children}*/}
        {/*  </div>*/}
        {/*</div>*/}
        {props?.children}
      </SidebarInset>
    </SidebarProvider>
  )
}
