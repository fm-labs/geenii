import React from 'react'
import { LogOutIcon, SettingsIcon, UserIcon, UserCogIcon } from 'lucide-react'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button.tsx'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { navdata } from '@/components/layout/navdata.ts'
import { useNavigate } from '@/app-router.tsx'

const userInitials = (name: string) => name.slice(0, 2).toUpperCase()

/** The user menu (stub: profile, settings and log out don't do anything yet) */
const UserMenu = () => {
  const navigate = useNavigate()
  const user = navdata.user

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" className="rounded-full" aria-label="User menu" title={user.name}>
          <Avatar className="size-8">
            <AvatarImage src={user.avatar} alt={user.name} />
            <AvatarFallback className="text-xs">{userInitials(user.name)}</AvatarFallback>
          </Avatar>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="min-w-56 rounded-lg" align="end" sideOffset={6}>
        <DropdownMenuLabel className="font-normal">
          <div className="grid text-sm leading-tight">
            <span className="truncate font-medium">{user.name}</span>
            <span className="truncate text-xs text-muted-foreground">{user.email}</span>
          </div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuGroup>
          <DropdownMenuItem disabled>
            <UserIcon />
            Profile
          </DropdownMenuItem>
          <DropdownMenuItem disabled>
            <UserCogIcon />
            Account settings
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => navigate('/console')}>
            <SettingsIcon />
            Console
          </DropdownMenuItem>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuItem disabled>
          <LogOutIcon />
          Log out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

/** Top bar of the launcher: brand on the left, console link and user menu on the right */
const LauncherHeader = () => {
  const navigate = useNavigate()

  return (
    <header className="fixed inset-x-0 top-0 z-50 flex h-12 items-center justify-between px-4 backdrop-blur-md">
      <span className="text-sm font-semibold tracking-tight">geenii</span>
      <div className="flex items-center gap-1">
        <Button variant="ghost" size="icon" aria-label="Console" title="Console" onClick={() => navigate('/console')}>
          <SettingsIcon />
        </Button>
        <UserMenu />
      </div>
    </header>
  )
}

export default LauncherHeader
