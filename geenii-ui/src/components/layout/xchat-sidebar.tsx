import * as React from "react"
import { MessageSquarePlusIcon, TrashIcon } from 'lucide-react'

import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupAction,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuAction,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from "@/components/ui/sidebar"
import { useChatSessions } from '@/components/xchat/chat-session-list.tsx'

/** The chat session list as a sidebar group. Must be used within a ChatProvider. */
const XchatSessionsGroup = () => {
  const { supported, canDelete, sessions, activeId, error, open, remove } = useChatSessions()

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
              <SidebarMenuButton isActive={session.id === activeId} onClick={() => open(session.id)}
                                 title={session.title || session.id}>
                <span className={'truncate'}>{session.title || session.id}</span>
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
  return (
    <Sidebar {...props}>
      {header && <SidebarHeader>{header}</SidebarHeader>}
      <SidebarContent>
        <XchatSessionsGroup />
      </SidebarContent>
      <SidebarRail />
    </Sidebar>
  )
}
