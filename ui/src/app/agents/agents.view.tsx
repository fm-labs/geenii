import React from 'react'
import { XAI_API_URL } from '@/constants.ts'
import { BotIcon, MessageCircleIcon } from 'lucide-react'
import { Badge } from '@/components/ui/badge.tsx'
import { Button } from '@/components/ui/button.tsx'
import Popup from '@/components/Popup.tsx'
import AgentChatRoom from '@/app/agents/agent-chat-room.tsx'
import { GeeChatContextProvider } from '@/app/geechat/geechat-context.tsx'

const AgentCard = ({ agent }: { agent: AgentType }) => {
  return (
    <div className="agent-card rounded-lg border p-4 flex flex-col justify-between hover:bg-accent hover:shadow-primary shadow-sm transition cursor-pointer">
      <div>
        <div className={"flex flex-row items-center justify-start mb-2 space-x-2"}>
          <BotIcon size={42} />
          <h3 className={"font-bold"}>{agent.name}</h3>
        </div>
        <p className={""}>{agent?.description}</p>
      </div>
      <div>
        <p className={"mt-2"}>{agent?.skills ? agent?.skills.map((s) => <Badge key={s}>{s}</Badge>) : 'No skills'}</p>
        <p className={"mt-2"}>{agent?.tools ? agent?.tools.map((t) => <Badge key={t} variant={"outline"}>{t}</Badge>) : 'No tools'}</p>

        <div className={"space-x-1 mt-4 text-right"}>
          {/*<Button size={"sm"} variant={"outline"}><BadgeInfoIcon /> About</Button>*/}
          {/*<Button size={"sm"} variant={"outline"}><PlusCircleIcon /> New Task</Button>*/}
          <AgentChatPopupButton agent={agent} />
        </div>
      </div>
    </div>
  )
}

const AgentChatPopupButton = ({ agent }: { agent: AgentType }) => {

  const [showChat, setShowChat] = React.useState(false)
  const [roomId, setRoomId] = React.useState<string>(null)

  React.useEffect(() => {
    if (showChat) {
      // Create or fetch chat room for this agent
      fetch(XAI_API_URL + 'api/v1/agents/' + agent.name + '/chat', {
        method: 'GET',
        headers: {
          "Content-Type": "application/json",
        }
      }).then(res => res.json()).then(data => {
        console.log("Chat room data", data)
        setRoomId(data.room_id)
      })
    }
  }, [showChat])

  return (
    <>
      <Button size={"sm"} variant={"outline"} onClick={() => setShowChat(!showChat)}><MessageCircleIcon /> Chat</Button>
      <Popup
        title={`Chat with ${agent.name}`}
        size="xl"
        showCloseButton={true}
        closeOnOverlayClick={true}
        show={showChat}
        onClose={() => setShowChat(false)}
      >
        <div className="max-w-4xl mx-auto">
          {roomId ? <GeeChatContextProvider roomId={roomId} username={'testuser'}>
            <div className="content">
              <div className="flex flex-col justify-center">
                <div className={'grow'}>
                  <AgentChatRoom />
                </div>
              </div>
            </div>
          </GeeChatContextProvider> : ('Loading...')}
        </div>
      </Popup>
    </>
  );
}

const AgentsView = () => {

  const [agents, setAgents] = React.useState<AgentType[]>([])

  const fetchAssistants = async () => {
    const response = await fetch(XAI_API_URL + 'api/v1/agents/', {
      headers: {
        "Content-Type": "application/json",
      }
    })
    const data = await response.json()
    console.log("Fetched assistants", data)
    return data?.agents || []
  }

  React.useEffect(() => {
    fetchAssistants().then(setAgents)
  }, [])

  return (
    <div>
      {agents.length > 0 ? (
        <div className={"grid sm:grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"}>
          {agents.map((agent, idx) => (
            <AgentCard key={`agent-${idx}-${agent.id}`} agent={agent} />
          ))}
        </div>
      ) : (
        <p>No agents found. Create a new agent to get started.</p>
      )}
    </div>
  )
}

export default AgentsView