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
  MessagesSquare, HelpingHand, BotMessageSquare,
} from 'lucide-react'
import { cn } from '@/lib/utils.ts'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar.tsx'
import { Button } from '@/components/ui/button.tsx'
import { ScrollArea } from '@/components/ui/scroll-area.tsx'
import { Separator } from '@/components/ui/separator.tsx'
import { NewChatDialog } from './components/new-chat-dialog.tsx'
import { type ChatUser, type Convo } from './chat-types.ts'
import Layout from '@/components/layout/layout.tsx'
import { id } from 'date-fns/locale'
import AssistantChat from '@/app/assistants/assistant-chat.tsx'
import ChatContextProvider from '@/app/chat/components/ChatContextProvider.tsx'
import AssistantChatList from '@/app/assistants/assistant-chat-list.tsx'
import { XAI_API_URL } from '@/constants.ts'
import '../chat/Chat.scss'
import { NewAssistantDialogButton } from '@/app/assistants/components/new-assistant-dialog-button.tsx'

export function AssistantChatsPage() {
  const [search, setSearch] = useState('')
  const [selectedUser, setSelectedUser] = useState<ChatUser | null>(null)
  const [mobileSelectedUser, setMobileSelectedUser] = useState<ChatUser | null>(
    null,
  )
  const [createConversationDialogOpened, setCreateConversationDialog] = useState(false)
  const [createAssistantDialogOpened, setCreateAssistantDialog] = useState(false)

  const [assistants, setAssistants] = useState<Assistant[]>()
  const [selectedAssistant, setSelectedAssistant] = useState<Assistant | null>(null)
  const [assistantChats, setAssistantChats] = useState<any[]>()
  const [selectedChat, setSelectedChat] = useState<any>()
  const [chatMessages, setChatMessages] = useState<any[]>()

  const fetchAssistants = async () => {
    const response = await fetch(XAI_API_URL + 'ai/v1/assistants/', {
      headers: {
        "Content-Type": "application/json",
      }
    })
    const data = await response.json()
    console.log("Fetched assistants", data)
    return data
  }

  const fetchAssistantChats = async (assistantId: string) => {
    const response = await fetch(XAI_API_URL + `ai/v1/assistants/${assistantId}/chats`, {
      headers: {
        "Content-Type": "application/json",
      }
    })
    const data = await response.json()
    console.log("Fetched assistant chats", data)
    return data
  }


  const fetchAssistantChat = async (assistantId: string, conversationId: string) => {
    console.log("Fetching AssistantChat messages", assistantId, conversationId)
    const response = await fetch(XAI_API_URL + `ai/v1/assistants/${assistantId}/chats/${conversationId}`, {
      headers: {
        "Content-Type": "application/json",
      }
    })
    const data = await response.json()
    console.log("Fetched assistant chat", data)
    return data
  }


  // const currentMessage = selectedUser?.messages.reduce(
  //   (acc: Record<string, Convo[]>, obj) => {
  //     const key = format(obj.timestamp, 'd MMM, yyyy')
  //
  //     // Create an array for the category if it doesn't exist
  //     if (!acc[key]) {
  //       acc[key] = []
  //     }
  //
  //     // Push the current object to the array
  //     acc[key].push(obj)
  //
  //     return acc
  //   },
  //   {},
  // )

  React.useEffect(() => {
    fetchAssistants().then((response) => setAssistants(response))
  }, [])

  React.useEffect(() => {
    if (selectedAssistant !== null) {
      setSelectedChat(undefined)
      fetchAssistantChats(selectedAssistant.id).then((response) => setAssistantChats(response))
    }
  }, [selectedAssistant])

  React.useEffect(() => {
    if (selectedAssistant && assistantChats && assistantChats.length > 0) {
      // find newest assistantChats by timestamp
      const sortedChats = assistantChats.sort((a, b) => a.timestamp - b.timestamp)
      setSelectedChat(sortedChats[sortedChats.length - 1])
      const lastConversationId = sortedChats[sortedChats.length - 1].id
      fetchAssistantChat(selectedAssistant.id, lastConversationId).then((response) => setChatMessages(response.messages))
    } else {
      setSelectedChat(undefined)
      setChatMessages([])
    }
  }, [assistantChats, selectedAssistant])

  // React.useEffect(() => {
  //   if (assistants && assistants.length > 0 && selectedAssistant === null) {
  //     setSelectedAssistant(assistants[0])
  //   }
  // }, [assistants, selectedAssistant])

  //const users = conversations.map(({ messages, ...user }) => user)

  const users = assistants ? assistants.map((assistant) => ({
    id: assistant.id,
    title: assistant.description,
    username: assistant.name,
    fullName: assistant.name,
    profile: assistant?.imageUrl,
    //messages: [],
  })) : []

  return (
    <Layout>
      <div className="flex flex-col gap-4 py-4 md:gap-6 md:py-6 px-4 flex-1 overflow-auto">
        <section className="flex h-full min-h-[90vh] gap-6">
          {/* Left Side */}
          <div className="flex w-full flex-col gap-2 sm:w-56 lg:w-72 2xl:w-80">
            <div
              className="bg-background sticky top-0 z-10 -mx-4 px-4 pb-3 shadow-md sm:static sm:z-auto sm:mx-0 sm:p-0 sm:shadow-none">
              <div className="flex items-center justify-between py-2">
                <div className="flex gap-2">
                  <h1 className="text-2xl font-bold">Assistants</h1>
                  <BotMessageSquare size={20} />
                </div>

                <Button
                  size="icon"
                  variant="ghost"
                  onClick={() => setCreateConversationDialog(true)}
                  className="rounded-lg"
                >
                  <Edit size={24} className="stroke-muted-foreground" />
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
                  placeholder="Search chat..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </label>
            </div>

            <ScrollArea className="-mx-3 h-full overflow-scroll p-3">
              <AssistantChatList assistants={assistants} selectedId={selectedUser?.id} onClickAssistant={(assistant) => {
                //setSelectedUser(assistant)
                //setMobileSelectedUser(assistant)
                setSelectedAssistant(assistant)
              }} />
              {/*filteredChatList.map((chatUsr) => {
                const { id, profile, username, messages, fullName } = chatUsr
                const lastConvo = messages[0]
                const lastMsg =
                  lastConvo.sender==='You'
                    ? `You: ${lastConvo.message}`
                    :lastConvo.message
                return (
                  <Fragment key={id}>
                    <button
                      type="button"
                      className={cn(
                        'group hover:bg-accent hover:text-accent-foreground',
                        `flex w-full rounded-md px-2 py-2 text-start text-sm`,
                        selectedUser?.id===id && 'sm:bg-muted',
                      )}
                      onClick={() => {
                        setSelectedUser(chatUsr)
                        setMobileSelectedUser(chatUsr)
                      }}
                    >
                      <div className="flex gap-2">
                        <Avatar>
                          <AvatarImage src={profile} alt={username} />
                          <AvatarFallback>{username}</AvatarFallback>
                        </Avatar>
                        <div>
                          <span className="col-start-2 row-span-2 font-medium">
                            {fullName}
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
              })*/}
            </ScrollArea>
          </div>

          {/* Right Side */}
          {selectedAssistant ? (
            <>
              <ChatContextProvider initialMessages={chatMessages}>
                <AssistantChat assistant={selectedAssistant} conversationId={selectedChat?.id}></AssistantChat>
              </ChatContextProvider>
            </>
          ):(
            <div
              className={cn(
                'bg-card absolute inset-0 start-full z-50 hidden w-full flex-1 flex-col justify-center rounded-md border shadow-xs sm:static sm:z-auto sm:flex',
              )}
            >
              <div className="flex flex-col items-center space-y-6">
                <div className="border-border flex size-16 items-center justify-center rounded-full border-2">
                  <MessagesSquare className="size-8" />
                </div>
                <div className="space-y-2 text-center">
                  <h1 className="text-xl font-semibold">Your messages</h1>
                  <p className="text-muted-foreground text-sm">
                    Send a message to start a chat.
                  </p>
                </div>
                <Button onClick={() => setCreateConversationDialog(true)}>
                  Send message
                </Button>

                <NewAssistantDialogButton
                  onOpenChange={setCreateAssistantDialog}
                  open={createAssistantDialogOpened}
                />
              </div>
            </div>
          )}
        </section>
        <NewChatDialog
          users={users}
          onOpenChange={setCreateConversationDialog}
          open={createConversationDialogOpened}
        />
        {/*<NewAssistantDialog />*/}
        {/*<AlertDialogDemo />*/}
      </div>
    </Layout>
  )
}
