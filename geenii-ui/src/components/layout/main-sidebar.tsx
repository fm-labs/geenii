'use client'

import * as React from 'react'
import {
  ArchiveX,
  BotIcon, CogIcon,
  Command,
  CommandIcon,
  File,
  Inbox,
  LayoutGridIcon, PlusSquareIcon,
  Send,
  ServerCogIcon,
  Trash2, WrenchIcon,
} from 'lucide-react'

import { NavUser } from '@/components/nav-user'
import { Label } from '@/components/ui/label'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarInput,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from '@/components/ui/sidebar'
import { Switch } from '@/components/ui/switch'
import { useNavigate } from '@/app-router.tsx'
import { useChatBackend, useChatSessions } from '@/components/xchat'
import { BackendSwitcher } from '@/components/xchat/backend-switcher.tsx'
import { useApi } from '@/context/api-context.tsx'

// This is sample data
const data = {
  user: {
    name: 'geenii',
    email: 'me@geenii.io',
    avatar: '/avatars/shadcn.jpg',
  },
  navMain: [
    // {
    //   title: 'Start',
    //   url: '#/',
    //   icon: LayoutGridIcon,
    //   isActive: true,
    // },
    {
      title: 'New Chat',
      url: '#/agents/default',
      icon: PlusSquareIcon,
      isActive: false,
    },
    {
      title: 'Agents',
      url: '#/agents',
      icon: BotIcon,
      isActive: false,
    },
    {
      title: 'Console',
      url: '#/console',
      icon: WrenchIcon,
      isActive: false,
    },
  ],
  mails: []
}

type MainSidebarProps = React.ComponentProps<typeof Sidebar> & {
  /** Rendered at the top of the sidebar, above the chat list */
  sidebarHeader?: React.ReactNode
}

export function MainSidebar({ sidebarHeader, ...props }: MainSidebarProps) {

  const [activeItem, setActiveItem] = React.useState(data.navMain[0])
  //const [mails, setMails] = React.useState(data.mails)
  const { setOpen } = useSidebar()
  const navigate = useNavigate()

  return (
    <Sidebar
      collapsible="icon"
      className="overflow-hidden *:data-[sidebar=sidebar]:flex-row"
      {...props}
    >
      {/* This is the first sidebar */}
      {/* We disable collapsible and adjust width to icon. */}
      {/* This will make the sidebar appear as icons. */}
      <Sidebar
        collapsible="none"
        className="w-[calc(var(--sidebar-width-icon)+1px)]! border-r"
      >
        <SidebarHeader>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton size="lg" asChild className="md:h-8 md:p-0">
                <a href="#/">
                  <div
                    className="flex aspect-square size-8 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
                    <LayoutGridIcon className="size-4" />
                  </div>
                  <div className="grid flex-1 text-left text-sm leading-tight">
                    <span className="truncate font-medium">Acme Inc</span>
                    <span className="truncate text-xs">Enterprise</span>
                  </div>
                </a>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarHeader>
        <SidebarContent>
          <SidebarGroup>
            <SidebarGroupContent className="px-1.5 md:px-0">
              <SidebarMenu>
                {data.navMain.map((item) => (
                  <SidebarMenuItem key={item.title}>
                    <SidebarMenuButton
                      tooltip={{
                        children: item.title,
                        hidden: false,
                      }}
                      onClick={() => {
                        setActiveItem(item)
                        // const mail = data.mails.sort(() => Math.random() - 0.5)
                        // setMails(
                        //   mail.slice(
                        //     0,
                        //     Math.max(5, Math.floor(Math.random() * 10) + 1)
                        //   )
                        // )
                        // setOpen(true)
                        setOpen(false)
                        navigate(item.url)
                      }}
                      isActive={activeItem?.title===item.title}
                      className="px-2.5 md:px-2"
                    >
                      <item.icon />
                      <span>{item.title}</span>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        </SidebarContent>
        <SidebarFooter>
          <NavUser user={data.user} />
        </SidebarFooter>
      </Sidebar>

      {/* This is the second sidebar */}
      {/* We disable collapsible and let it fill remaining space */}
      <Sidebar collapsible="none" className="hidden flex-1 md:flex">
        <SidebarHeader className="gap-3.5 border-b p-4">
          {sidebarHeader}
        </SidebarHeader>
        <SidebarHeader className="gap-3.5 border-b p-4">
          <div className="flex w-full items-center justify-between">
            <div className="text-base font-medium text-foreground">
              {activeItem?.title}
            </div>
            <Label className="flex items-center gap-2 text-sm">
              <span>Unreads</span>
              <Switch className="shadow-none" />
            </Label>
          </div>
          <SidebarInput placeholder="Type to search..." />
        </SidebarHeader>
        <SidebarContent>
          {/*<SidebarGroup className="px-0">*/}
          {/*  <SidebarGroupContent>*/}
          {/*    {mails.map((mail) => (*/}
          {/*      <a*/}
          {/*        href="#"*/}
          {/*        key={mail.email}*/}
          {/*        className="flex flex-col items-start gap-2 border-b p-4 text-sm leading-tight whitespace-nowrap last:border-b-0 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"*/}
          {/*      >*/}
          {/*        <div className="flex w-full items-center gap-2">*/}
          {/*          <span>{mail.name}</span>{' '}*/}
          {/*          <span className="ml-auto text-xs">{mail.date}</span>*/}
          {/*        </div>*/}
          {/*        <span className="font-medium">{mail.subject}</span>*/}
          {/*        <span className="line-clamp-2 w-[260px] text-xs whitespace-break-spaces">*/}
          {/*          {mail.teaser}*/}
          {/*        </span>*/}
          {/*      </a>*/}
          {/*    ))}*/}
          {/*  </SidebarGroupContent>*/}
          {/*</SidebarGroup>*/}
          <XchatSessionsSidebarGroup />
        </SidebarContent>
      </Sidebar>
    </Sidebar>
  )
}

/** The chat session list as a sidebar group. Must be used within a ChatProvider. */
const XchatSessionsSidebarGroup = () => {
  let backend
  let chatSessions;
  try {
    backend = useChatBackend()
    chatSessions = useChatSessions()
  } catch (error) {
    return <div>Failed to load sidebar group</div>
  }
  const { supported, canDelete, sessions, activeId, error, open, remove } = chatSessions

  if (error) {
    return <div>Failed to load sidebar group</div>
  }

  const _truncate = (str: string, maxLength: number) => {
    if (str.length <= maxLength) {
      return str;
    }
    return str.substring(0, maxLength) + '...';
  }

  const _formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleString();
  }

  const filtered = React.useMemo(() => {
      return sessions.filter((s) =>
        s.agent === backend.id.substring('agent:'.length)
      )
    }, [sessions, backend.id])

  return (
    <SidebarGroup className="px-0">
      <SidebarGroupContent>
        {filtered && filtered.map((session) => (
          <a
            href={`#/agents/${session.agent}/${session.id}`}
            key={session.id}
            //onClick={() => open(session.id)}
            className="flex flex-col items-start gap-2 border-b p-2 text-sm leading-tight whitespace-nowrap last:border-b-0 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
          >
            <div className="flex w-full items-center gap-2">
              <span className={"text-muted-foreground"}>{session.agent}</span>{' '}
              <span className="ml-auto text-xs text-muted-foreground">{_formatDate(session.updated_at)}</span>
            </div>
            <span
              className="font-medium">{session.title ? _truncate(session.title, 35) : 'Untitled'}</span>
            {/*<span className="line-clamp-2 w-[260px] text-xs whitespace-break-spaces text-muted-foreground">*/}
            {/*  {session.id}*/}
            {/*</span>*/}
          </a>
        ))}
      </SidebarGroupContent>
    </SidebarGroup>)
}
