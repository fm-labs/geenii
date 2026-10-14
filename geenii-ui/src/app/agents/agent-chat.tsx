import React from 'react'
import { BotIcon, MessageSquarePlusIcon } from 'lucide-react'
import { Button } from '@/components/ui/button.tsx'
import { Chat, ChatProvider, ChatVoiceInput, createAgentBackend, useChat } from '@/components/xchat'
import { useApi } from '@/context/api-context.tsx'
import useNotification from '@/hooks/useNotification.ts'
import { FEATURE_VOICE_RECORDING_ENABLED } from '@/constants.ts'
import { AgentType } from '@/app/agents/agent-types.ts'

const AgentChatHeader = ({ children, onNewChat }: { children: React.ReactNode, onNewChat: () => void }) => {
  const hasMessages = useChat((s) => s.messages.length > 0)
  const contextId = useChat((s) => s.contextId)

  return (
    <div className="flex shrink-0 items-center gap-2 border-b pb-2">
      <div className="min-w-0 flex-1">{children}</div>
      <Button size="sm" variant="ghost" onClick={onNewChat} disabled={!hasMessages}
              title={contextId ? `Current conversation: ${contextId}` : 'New conversation'}>
        <MessageSquarePlusIcon /> <span className="hidden sm:inline">New chat</span>
      </Button>
    </div>
  )
}

/**
 * xchat bound to one agent: each conversation is a new /chats session with this agent.
 * There is no session list; "New chat" starts over (the previous session stays on the server).
 */
const AgentChat = ({ agent, header, className }: {
  agent: AgentType
  /** Left part of the card header, e.g. the agent's short info; defaults to the agent's name */
  header?: React.ReactNode
  className?: string
}) => {
  const { apiBaseUrl } = useApi()
  const notify = useNotification()
  const title = agent.label || agent.name

  const backend = React.useMemo(
    () => createAgentBackend({ baseUrl: apiBaseUrl, agent: agent.name }),
    [apiBaseUrl, agent.name],
  )

  // remounting the provider starts a fresh conversation (and cancels a running turn)
  const [chatKey, setChatKey] = React.useState(0)

  return (
    <div className={`flex flex-col ${className ?? ''}`}>
      <ChatProvider key={chatKey} backend={backend} onError={(error) => notify.error(error)}>
        <AgentChatHeader onNewChat={() => setChatKey((k) => k + 1)}>
          {header ?? <h3 className="truncate text-sm font-semibold">{title}</h3>}
        </AgentChatHeader>
        <div className="min-h-0 flex-1 overflow-y-auto">
          <Chat
            className="mx-auto min-h-full w-full max-w-3xl px-4"
            placeholder={`Message ${title} …`}
            empty={
              <div className="flex flex-col items-center gap-2 text-center">
                <div className="rounded-full bg-muted p-3 text-muted-foreground"><BotIcon size={24} /></div>
                <h4 className="font-semibold">{title}</h4>
                {agent.description && (
                  <p className="max-w-md text-sm text-muted-foreground line-clamp-3">{agent.description.trim()}</p>
                )}
                <p className="text-xs text-muted-foreground">Type <kbd className="font-mono">/</kbd> for commands</p>
              </div>
            }
            inputAddons={FEATURE_VOICE_RECORDING_ENABLED && <ChatVoiceInput />}
          />
        </div>
      </ChatProvider>
    </div>
  )
}

export default AgentChat
