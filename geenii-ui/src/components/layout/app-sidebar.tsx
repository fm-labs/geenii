'use client'

import * as React from 'react'
import { ArchiveX, Command, File, Inbox, Send, Trash2 } from 'lucide-react'

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
import { useChatSessions } from '@/components/xchat'
import { BackendSwitcher } from '@/components/backend-switcher.tsx'
import { useApi } from '@/context/api-context.tsx'

// This is sample data
const data = {
  user: {
    name: 'shadcn',
    email: 'm@example.com',
    avatar: '/avatars/shadcn.jpg',
  },
  navMain: [
    {
      title: 'Start',
      url: '#/',
      icon: Inbox,
      isActive: true,
    },
    {
      title: 'Agents',
      url: '#/agents',
      icon: File,
      isActive: false,
    },
    {
      title: 'Sent',
      url: '#/console',
      icon: Send,
      isActive: false,
    },
    {
      title: 'Junk',
      url: '#',
      icon: ArchiveX,
      isActive: false,
    },
    {
      title: 'Trash',
      url: '#',
      icon: Trash2,
      isActive: false,
    },
  ],
  mails: [
    {
      name: 'William Smith',
      email: 'williamsmith@example.com',
      subject: 'Meeting Tomorrow',
      date: '09:34 AM',
      teaser:
        'Hi team, just a reminder about our meeting tomorrow at 10 AM.\nPlease come prepared with your project updates.',
    },
    {
      name: 'Alice Smith',
      email: 'alicesmith@example.com',
      subject: 'Re: Project Update',
      date: 'Yesterday',
      teaser:
        'Thanks for the update. The progress looks great so far.\nLet\'s schedule a call to discuss the next steps.',
    },
    {
      name: 'Bob Johnson',
      email: 'bobjohnson@example.com',
      subject: 'Weekend Plans',
      date: '2 days ago',
      teaser:
        'Hey everyone! I\'m thinking of organizing a team outing this weekend.\nWould you be interested in a hiking trip or a beach day?',
    },
    {
      name: 'Emily Davis',
      email: 'emilydavis@example.com',
      subject: 'Re: Question about Budget',
      date: '2 days ago',
      teaser:
        'I\'ve reviewed the budget numbers you sent over.\nCan we set up a quick call to discuss some potential adjustments?',
    },
    {
      name: 'Michael Wilson',
      email: 'michaelwilson@example.com',
      subject: 'Important Announcement',
      date: '1 week ago',
      teaser:
        'Please join us for an all-hands meeting this Friday at 3 PM.\nWe have some exciting news to share about the company\'s future.',
    },
    {
      name: 'Sarah Brown',
      email: 'sarahbrown@example.com',
      subject: 'Re: Feedback on Proposal',
      date: '1 week ago',
      teaser:
        'Thank you for sending over the proposal. I\'ve reviewed it and have some thoughts.\nCould we schedule a meeting to discuss my feedback in detail?',
    },
    {
      name: 'David Lee',
      email: 'davidlee@example.com',
      subject: 'New Project Idea',
      date: '1 week ago',
      teaser:
        'I\'ve been brainstorming and came up with an interesting project concept.\nDo you have time this week to discuss its potential impact and feasibility?',
    },
    {
      name: 'Olivia Wilson',
      email: 'oliviawilson@example.com',
      subject: 'Vacation Plans',
      date: '1 week ago',
      teaser:
        'Just a heads up that I\'ll be taking a two-week vacation next month.\nI\'ll make sure all my projects are up to date before I leave.',
    },
    {
      name: 'James Martin',
      email: 'jamesmartin@example.com',
      subject: 'Re: Conference Registration',
      date: '1 week ago',
      teaser:
        'I\'ve completed the registration for the upcoming tech conference.\nLet me know if you need any additional information from my end.',
    },
    {
      name: 'Sophia White',
      email: 'sophiawhite@example.com',
      subject: 'Team Dinner',
      date: '1 week ago',
      teaser:
        'To celebrate our recent project success, I\'d like to organize a team dinner.\nAre you available next Friday evening? Please let me know your preferences.',
    },
  ],
}

type AppSidebarProps = React.ComponentProps<typeof Sidebar> & {
  /** Rendered at the top of the sidebar, above the chat list */
  sidebarHeader?: React.ReactNode
}

export function AppSidebar({ sidebarHeader, ...props }: AppSidebarProps) {

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
                    <Command className="size-4" />
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

  let chatSessions;
  try {
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

  return (
    <SidebarGroup className="px-0">
      <SidebarGroupContent>
        {sessions !== undefined && sessions.map((session) => (
          <a
            href={`#/agents/${session.agent}`}
            key={session.id}
            onClick={() => open(session.id)}
            className="flex flex-col items-start gap-2 border-b p-4 text-sm leading-tight whitespace-nowrap last:border-b-0 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
          >
            <div className="flex w-full items-center gap-2">
              <span>{session.agent}</span>{' '}
              <span className="ml-auto text-xs">{_formatDate(session.updated_at)}</span>
            </div>
            <span
              className="font-medium">{session.title ? _truncate(session.title, 35) : 'Untitled'}</span>
            <span className="line-clamp-2 w-[260px] text-xs whitespace-break-spaces">
              {session.id}
            </span>
          </a>
        ))}
      </SidebarGroupContent>
    </SidebarGroup>)
}
