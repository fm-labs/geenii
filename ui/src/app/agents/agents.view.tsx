import React from 'react'
import Header from '@/components/header.tsx'
import { XAI_API_URL } from '@/constants.ts'
import { BadgeInfoIcon, BotIcon, CheckCircleIcon, MessageCircleIcon, PlusCircleIcon } from 'lucide-react'
import { Badge } from '@/components/ui/badge.tsx'
import { Button } from '@/components/ui/button.tsx'

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
        <p className={"mt-2"}>{agent?.skills ? agent?.skills.map((s) => <Badge>{s}</Badge>) : 'No skills'}</p>
        <p className={"mt-2"}>{agent?.tools ? agent?.tools.map((t) => <Badge variant={"outline"}>{t}</Badge>) : 'No tools'}</p>

        <div className={"space-x-1 mt-4 text-right"}>
          <Button size={"sm"} variant={"outline"}><BadgeInfoIcon /> About</Button>
          <Button size={"sm"} variant={"outline"}><MessageCircleIcon /> Chat</Button>
          <Button size={"sm"} variant={"outline"}><PlusCircleIcon /> New Task</Button>
        </div>
      </div>
    </div>
  )
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
          {agents.map((agent) => (
            <AgentCard key={agent.name} agent={agent} />
          ))}
        </div>
      ) : (
        <p>No agents found. Create a new agent to get started.</p>
      )}
    </div>
  )
}

export default AgentsView