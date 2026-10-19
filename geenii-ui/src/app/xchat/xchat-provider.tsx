import React, { PropsWithChildren } from 'react'
import useNotification from '@/hooks/useNotification.ts'
import { useApi } from '@/context/api-context.tsx'
import {
  ChatProvider,
  createAgentBackend,
  createEchoBackend,
} from '@/components/xchat'
import MainLayout from '@/components/layout/main-layout.tsx'
import { BackendSwitcher } from '@/components/xchat/backend-switcher.tsx'

const ECHO = 'echo'

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

const XchatProvider = (props: PropsWithChildren<{
  defaultBackend?: string
}>) => {
  const notify = useNotification()
  const { apiBaseUrl } = useApi()
  const agentNames = useAgentNames()
  const [selectedBackend, setSelectedBackend] = React.useState<string>(props.defaultBackend || 'default')

  const backend = React.useMemo(() => {
    if (selectedBackend===ECHO || !apiBaseUrl) return createEchoBackend({ delay: 500 })
    return createAgentBackend({ baseUrl: apiBaseUrl, agent: selectedBackend })
  }, [selectedBackend, apiBaseUrl])

  return (
    <ChatProvider backend={backend} onError={(error) => notify.error(error)}>
      <MainLayout sidebarHeader={
                     <BackendSwitcher backends={[ECHO, ...agentNames]} defaultBackend={selectedBackend} onChange={setSelectedBackend} />
                  }>
        {props.children}
      </MainLayout>
    </ChatProvider>
  )
}

export default XchatProvider
