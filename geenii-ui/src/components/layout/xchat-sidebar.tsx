import * as React from 'react'
import { MessageSquarePlusIcon, TrashIcon } from 'lucide-react'

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupAction,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuAction,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail, useSidebar,
} from '@/components/ui/sidebar'
import { useChatSessions } from '@/components/xchat/chat-session-list.tsx'
import { NavUser } from '@/components/nav-user.tsx'
import { useNavigate } from '@/app-router.tsx'
import { navdata } from '@/components/layout/navdata.ts'
import { storeSidebarOpenState } from '@/components/layout/xchat-layout-helper.ts'
import { consoleNavData } from '@/components/layout/console-navdata.tsx'
import { xchatNavData } from '@/components/layout/xchat-navdata.tsx'

/** The chat session list as a sidebar group. Must be used within a ChatProvider. */
const XchatSessionsGroup = () => {
  const { supported, canDelete, sessions, activeId, error, open, remove } = useChatSessions()
  const navigate = useNavigate()
  return (
    <SidebarGroup>
      <SidebarGroupLabel>Chats</SidebarGroupLabel>
      <SidebarGroupAction title={'New chat'} onClick={() => open(null)}>
        <MessageSquarePlusIcon /> <span className={'sr-only'}>New chat</span>
      </SidebarGroupAction>
      <SidebarGroupContent>
        {error && <div className={'px-2 py-1 text-xs text-destructive'}>{error}</div>}
        {!supported && <div className={'px-2 py-1 text-xs text-muted-foreground'}>This backend keeps no chat history.</div>}
        {supported && sessions.length === 0 && !error && (
          <div className={'px-2 py-1 text-xs text-muted-foreground'}>No chats yet.</div>
        )}
        <SidebarMenu>
          {sessions.map((session) => (
            <SidebarMenuItem key={session.id}>
              <SidebarMenuButton size={session.agent ? 'lg' : 'default'} isActive={session.id === activeId}
                                 //onClick={() => open(session.id)}
                                 onClick={() => navigate(`/agents/${session.agent}/${session.id}`)}
                                 title={session.agent ? `${session.title || session.id} (${session.agent})` : session.title || session.id}>
                <div className={'flex min-w-0 flex-col'}>
                  <span className={'truncate'}>{session.title || session.id}</span>
                  {session.agent && <span className={'truncate text-xs text-muted-foreground'}>{session.agent}</span>}
                </div>
              </SidebarMenuButton>
              {canDelete && (
                <SidebarMenuAction showOnHover title={'Delete chat'} onClick={() => remove(session.id)}>
                  <TrashIcon /> <span className={'sr-only'}>Delete chat</span>
                </SidebarMenuAction>
              )}
            </SidebarMenuItem>
          ))}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  )
}

export function XchatSidebar({ header, ...props }: React.ComponentProps<typeof Sidebar> & {
  /** Rendered above the chat list, e.g. a backend / agent picker */
  header?: React.ReactNode
}) {
  const {open} = useSidebar()

  // track the sidebar state in localstorage
  React.useEffect(() => {
    storeSidebarOpenState(open)
  }, [open])

  return (
    <Sidebar {...props}>
      {header && <SidebarHeader>{header}</SidebarHeader>}
      <SidebarContent>
        {xchatNavData.navMain.map((item) => (
          <SidebarGroup key={item.title}>
            <SidebarGroupLabel>{item.title}</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {item.items.map((item) => (
                  <SidebarMenuItem key={item.title}>
                    <SidebarMenuButton asChild /*isActive={item.isActive}*/>
                      <a href={item.url}>{item.title}</a>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        ))}

        <XchatSessionsGroup />
      </SidebarContent>
      <SidebarRail />
      <SidebarFooter>
        <NavUser user={navdata.user} />
      </SidebarFooter>
    </Sidebar>
  )
}
