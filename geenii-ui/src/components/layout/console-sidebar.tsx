import * as React from 'react'

import { SearchForm } from '@/components/search-form'
import {
  Sidebar,
  SidebarContent, SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from '@/components/ui/sidebar'
import { navdata } from '@/components/layout/navdata.ts'
import { NavUser } from '@/components/nav-user.tsx'
import { consoleNavData } from '@/components/layout/console-navdata.tsx'
//import { data as settingsNavData } from '@/app/console/settings-navdata.tsx'

export function ConsoleSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  return (
    <Sidebar {...props}>
      <SidebarHeader>
        <div className={"font-bold p-4 mb-2 border-b"}>
          GEENII CONSOLE
        </div>
        <SearchForm />
      </SidebarHeader>
      <SidebarContent>
        {/* We create a SidebarGroup for each parent. */}
        {consoleNavData.navMain.map((item) => (
          <SidebarGroup key={item.title}>
            <SidebarGroupLabel>{item.title}</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {item.items.map((item: any) => (
                  <SidebarMenuItem key={item.title}>
                    <SidebarMenuButton asChild /*isActive={item.isActive}*/>
                      {/*item?.icon && <item.icon />*/}
                      <a href={item.url}>{item.title}</a>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        ))}

        {/*<SidebarGroup>*/}
        {/*  <SidebarGroupContent>*/}
        {/*    <SidebarMenu>*/}
        {/*      {settingsNavData.nav.map((item) => (*/}
        {/*        <SidebarMenuItem key={item.name}>*/}
        {/*          <SidebarMenuButton>*/}
        {/*            <>*/}
        {/*              <item.icon />*/}
        {/*              <span>{item.name}</span>*/}
        {/*            </>*/}
        {/*          </SidebarMenuButton>*/}
        {/*        </SidebarMenuItem>*/}
        {/*      ))}*/}
        {/*    </SidebarMenu>*/}
        {/*  </SidebarGroupContent>*/}
        {/*</SidebarGroup>*/}
      </SidebarContent>
      <SidebarRail />
      <SidebarFooter>
        <NavUser user={navdata.user} />
      </SidebarFooter>
    </Sidebar>
  )
}
