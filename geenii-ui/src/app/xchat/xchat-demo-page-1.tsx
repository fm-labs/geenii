import React from 'react'
import useNotification from '@/hooks/useNotification.ts'
import { FEATURE_VOICE_RECORDING_ENABLED } from '@/constants.ts'
import { useApi } from '@/context/api-context.tsx'
import {
  Chat,
  ChatProvider,
  ChatVoiceInput,
  createAgentBackend,
  createEchoBackend,
  useChat,
} from '@/components/xchat'
import XchatLayout from '@/components/layout/xchat-layout.tsx'
import { BackendSwitcher } from '@/components/backend-switcher.tsx'

const ECHO = 'echo'

const ChatDebugStatus = () => {
  const { status, contextId } = useChat((s) => ({ status: s.status, contextId: s.contextId }))
  return <div className={'text-muted-foreground text-xs italic'}>
    {status}{contextId && ` · context ${contextId}`}
  </div>
}

const useAgentNames = () => {
  const { fetchJson } = useApi()
  const [names, setNames] = React.useState<string[]>([])
  React.useEffect(() => {
    fetchJson('/api/v1/agents/')
      .then((agents: { name: string }[]) => setNames(agents.map((a) => a.name)))
      .catch(() => setNames([]))
  }, [fetchJson])
  return names
}

const XchatDemoPage1 = () => {
  const notify = useNotification()
  const { apiBaseUrl } = useApi()
  const agentNames = useAgentNames()
  const [selected, setSelected] = React.useState<string>(ECHO)

  const backend = React.useMemo(() => {
    if (selected===ECHO || !apiBaseUrl) return createEchoBackend({ delay: 500 })
    return createAgentBackend({ baseUrl: apiBaseUrl, agent: selected })
  }, [selected, apiBaseUrl])

  return (
    <ChatProvider backend={backend} onError={(error) => notify.error(error)}>
      <XchatLayout sidebarHeader={
         <BackendSwitcher backends={[ECHO, ...agentNames]} defaultBackend={selected} onChange={setSelected} />
      }>
        <Chat
          className={'w-full max-w-3xl mx-auto px-4 min-h-svh'}
          empty={<div className={'text-center'}>
            <h2 className={'text-2xl font-semibold'}>What can I do for you?</h2>
            {selected === ECHO && <p className={'mt-2 text-sm text-muted-foreground'}>
              Echo backend: send "example" for one message of each type, or start with "tool" for a tool approval.
            </p>}
          </div>}
          inputAddons={FEATURE_VOICE_RECORDING_ENABLED && <ChatVoiceInput />}
          footer={<ChatDebugStatus />}
        />
      </XchatLayout>
    </ChatProvider>
  )
}

export default XchatDemoPage1
