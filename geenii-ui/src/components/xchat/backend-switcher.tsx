'use client'

import * as React from 'react'
import { Check, ChevronsUpDown, GalleryVerticalEnd } from 'lucide-react'

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu.tsx'
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from '@/components/ui/sidebar.tsx'
import { useChatBackend } from '@/components/xchat/chat-context.tsx'

export function BackendSwitcher({
                                  backends,
                                  defaultBackend, onChange,
                                }: {
  backends: string[]
  defaultBackend: string
  onChange: (selected: string) => void
}) {
  const [selectedBackend, setSelectedBackend] = React.useState(defaultBackend)

  const backend = useChatBackend()
  React.useEffect(() => {
    if (backend?.id?.startsWith('agent:')) {
      setSelectedBackend(backend.id.substring('agent:'.length))
    } else if (backend?.id) {
      setSelectedBackend(backend.id)
    }
  }, [backend.id])

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton
              size="lg"
              className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
            >
              <div
                className="flex aspect-square size-8 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
                <GalleryVerticalEnd className="size-4" />
              </div>
              <div className="flex flex-col gap-0.5 leading-none">
                <span className="font-medium">Agent</span>
                <span className="">{selectedBackend}</span>
              </div>
              <ChevronsUpDown className="ml-auto" />
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            className="w-(--radix-dropdown-menu-trigger-width)"
            align="start"
          >
            {backends.map((backend) => (
              <DropdownMenuItem
                key={backend}
                onSelect={() => {
                  setSelectedBackend(backend)
                  if (onChange) {
                    onChange(backend)
                  }
                }}
              >
                {backend}{' '}
                {backend===selectedBackend && <Check className="ml-auto" />}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}
