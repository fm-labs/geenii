import React, { useState } from 'react'
import { Fragment } from 'react/jsx-runtime'
import { format } from 'date-fns'
import {
  ArrowLeft,
  MoreVertical,
  Edit,
  Paperclip,
  Phone,
  ImagePlus,
  Plus,
  Search as SearchIcon,
  Send,
  Video,
  MessagesSquare, ServerIcon,
} from 'lucide-react'
import { cn } from '@/lib/utils.ts'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar.tsx'
import { Button } from '@/components/ui/button.tsx'
import { ScrollArea } from '@/components/ui/scroll-area.tsx'
import { Separator } from '@/components/ui/separator.tsx'
import Layout from '@/components/layout/layout.tsx'
import { useMcpServers } from '@/app/mcp-servers/components/mcp-servers-provider.tsx'
import { McpServer } from '@/app/mcp-servers/components/mcp-server.tsx'
import { McpServerProvider } from '@/app/mcp-servers/components/mcp-server-provider.tsx'
import McpServerViewHead from '@/app/mcp-servers/components/mcp-server-view-head.tsx'
import McpServerActions from '@/app/mcp-servers/components/mcp-server-actions.tsx'

export function McpServersView() {
  const { servers } = useMcpServers()
  const [search, setSearch] = useState('')

  //const servers: any[] = []
  const [selectedServer, setSelectedServer] = useState<any | null>(null)

  return (
    <>
      <div className="flex flex-col gap-4 py-4 md:gap-6 md:py-6 px-4 flex-1 overflow-auto">
        <section className="flex h-full min-h-[90vh] gap-6">
          {/* Left Side */}
          <div className="flex w-full flex-col gap-2 sm:w-56 lg:w-72 2xl:w-80">
            <div
              className="bg-background sticky top-0 z-10 -mx-4 px-4 pb-3 shadow-md sm:static sm:z-auto sm:mx-0 sm:p-0 sm:shadow-none">
              <div className="flex items-center justify-between py-2">
                <div className="flex gap-2">
                  <h1 className="text-2xl font-bold">MCP Servers</h1>
                  {/*<MessagesSquare size={20} />*/}
                </div>

                <Button
                  size="icon"
                  variant="ghost"
                  //onClick={() => setCreateConversationDialog(true)}
                  className="rounded-lg"
                  title={'Add MCP Server'}
                >
                  <Plus size={24} className="stroke-muted-foreground" />
                </Button>
              </div>

              <label
                className={cn(
                  'focus-within:ring-ring focus-within:ring-1 focus-within:outline-hidden',
                  'border-border flex h-10 w-full items-center space-x-0 rounded-md border ps-2',
                )}
              >
                <SearchIcon size={15} className="me-2 stroke-slate-500" />
                <span className="sr-only">Search</span>
                <input
                  type="text"
                  className="w-full flex-1 bg-inherit text-sm focus-visible:outline-hidden"
                  placeholder="Search server..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </label>
            </div>

            <ScrollArea className="-mx-3 h-full overflow-scroll p-3">
              {servers.map((server) => {
                const { name, type } = server
                const lastMsg = 'not connected'
                return (
                  <Fragment key={name}>
                    <button
                      type="button"
                      className={cn(
                        'group hover:bg-accent hover:text-accent-foreground',
                        `flex w-full rounded-md px-2 py-2 text-start text-sm`,
                        selectedServer?.name===name && 'sm:bg-muted',
                      )}
                      onClick={() => {
                        setSelectedServer(server)
                      }}
                    >
                      <div className="flex gap-2">
                        <Avatar>
                          <AvatarImage src={undefined} alt={name} />
                          <AvatarFallback>{name}</AvatarFallback>
                        </Avatar>
                        <div>
                          <span className="col-start-2 row-span-2 font-medium">
                            {name}
                          </span>
                          <span
                            className="text-muted-foreground group-hover:text-accent-foreground/90 col-start-2 row-span-2 row-start-2 line-clamp-2 text-ellipsis">
                            {lastMsg}
                          </span>
                        </div>
                      </div>
                    </button>
                    <Separator className="my-1" />
                  </Fragment>
                )
              })}
            </ScrollArea>
          </div>

          {/* Right Side */}
          {selectedServer ? (
            <div
              className={cn(
                'bg-background absolute inset-0 start-full z-50 hidden w-full flex-1 flex-col border shadow-xs sm:static sm:z-auto sm:flex sm:rounded-md',
                selectedServer && 'start-0 flex',
              )}
            >
              <McpServerProvider server={selectedServer} serverName={selectedServer.name}>
                {/* Top Part */}
                <McpServerViewHead />

                {/* Conversation */}
                <div className="flex flex-1 flex-col gap-2 rounded-md px-4 pt-0 pb-4">
                  <div className="flex size-full flex-1">
                    <div className="chat-text-container relative -me-4 flex flex-1 flex-col overflow-y-hidden">
                      <div
                        className="chat-flex flex h-40 w-full grow flex-col justify-start gap-4 overflow-y-auto py-2 pe-4 pb-4">

                        <McpServer />
                        <McpServerActions />
                      </div>
                    </div>
                  </div>
                  {/*<form className="flex w-full flex-none gap-2">
                    <div
                      className="border-input bg-card focus-within:ring-ring flex flex-1 items-center gap-2 rounded-md border px-2 py-1 focus-within:ring-1 focus-within:outline-hidden lg:gap-4">
                      <div className="space-x-1">
                        <Button
                          size="icon"
                          type="button"
                          variant="ghost"
                          className="h-8 rounded-md"
                        >
                          <Plus size={20} className="stroke-muted-foreground" />
                        </Button>
                        <Button
                          size="icon"
                          type="button"
                          variant="ghost"
                          className="hidden h-8 rounded-md lg:inline-flex"
                        >
                          <ImagePlus
                            size={20}
                            className="stroke-muted-foreground"
                          />
                        </Button>
                        <Button
                          size="icon"
                          type="button"
                          variant="ghost"
                          className="hidden h-8 rounded-md lg:inline-flex"
                        >
                          <Paperclip
                            size={20}
                            className="stroke-muted-foreground"
                          />
                        </Button>
                      </div>
                      <label className="flex-1">
                        <span className="sr-only">Chat Text Box</span>
                        <input
                          type="text"
                          placeholder="Type your messages..."
                          className="h-8 w-full bg-inherit focus-visible:outline-hidden"
                        />
                      </label>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="hidden sm:inline-flex"
                      >
                        <Send size={20} />
                      </Button>
                    </div>
                    <Button className="h-full sm:hidden">
                      <Send size={18} /> Send
                    </Button>
                  </form>*/}
                </div>
              </McpServerProvider>
            </div>
          ):(
            <div
              className={cn(
                'bg-card absolute inset-0 start-full z-50 hidden w-full flex-1 flex-col justify-center rounded-md border shadow-xs sm:static sm:z-auto sm:flex',
              )}
            >
              <div className="flex flex-col items-center space-y-6">
                <div className="border-border flex size-16 items-center justify-center rounded-full border-2">
                  <ServerIcon className="size-8" />
                </div>
                <div className="space-y-2 text-center">
                  <h1 className="text-xl font-semibold">Your MCP Servers</h1>
                  <p className="text-muted-foreground text-sm">
                    Select an existing MCP Server, add a new one
                    or checkout the server catalog to get started.
                  </p>
                </div>
                <Button onClick={() => console.log('clicked')}>
                  Add MCP Server
                </Button>
                <Button asChild>
                  <a href="#/mcp/docker">View Docker MCP Catalog</a>
                </Button>
              </div>
            </div>
          )}
        </section>
        {/*<NewChat
          users={users}
          onOpenChange={setCreateConversationDialog}
          open={createConversationDialogOpened}
        />*/}
      </div>
    </>
  )
}
