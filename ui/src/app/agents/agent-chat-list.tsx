import React from 'react'
import { Fragment } from 'react/jsx-runtime'
import { cn } from '@/lib/utils.ts'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar.tsx'
import { Separator } from '@/components/ui/separator.tsx'

interface AgentChatListProps {
  agents: Agent[]
  selectedId: string
  onClickAgent: (agent: Agent) => void
}

const AgentChatList = (props: AgentChatListProps) => {
  const filteredChatList = props?.agents || []

  const handleUserClick = (agent: any) => {
    if (props.onClickAgent) {
      props.onClickAgent(agent)
    }
  }

  return (
    <div>
      {filteredChatList.map((agent) => {
        const { id, name, description, model} = agent
        // const lastConvo = messages[0]
        // const lastMsg =
        //   lastConvo.sender === 'You'
        //     ? `You: ${lastConvo.message}`
        //     : lastConvo.message
        const lastMsg = model || 'No description available.'
        const username = id;
        const profile = agent.imageUrl || '/default-agent.png'
        return (
          <Fragment key={id}>
            <button
              type='button'
              className={cn(
                'group hover:bg-accent hover:text-accent-foreground',
                `flex w-full rounded-md px-2 py-2 text-start text-sm`,
                props?.selectedId === id && 'sm:bg-muted'
              )}
              onClick={() => {
                handleUserClick(agent)
              }}
            >
              <div className='flex gap-2'>
                <Avatar>
                  <AvatarImage src={profile} alt={username} />
                  <AvatarFallback>{username}</AvatarFallback>
                </Avatar>
                <div>
                          <span className='col-start-2 row-span-2 font-medium'>
                            {name}
                          </span>
                  <span className='text-muted-foreground group-hover:text-accent-foreground/90 col-start-2 row-span-2 row-start-2 line-clamp-2 text-ellipsis'>
                            {lastMsg}
                          </span>
                </div>
              </div>
            </button>
            <Separator className='my-1' />
          </Fragment>
        )
      })}
    </div>
  )
}

export default AgentChatList