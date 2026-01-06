import React from 'react'
import CompletionChatPage from '@/app/chat/completion-chat-page.tsx'
import WelcomeScreen from '@/app/welcome/WelcomeScreen.tsx'
import McpServersPage from '@/app/mcp-servers/mcp-servers-page.tsx'
import DockerCatalogPage from '@/app/mcp-servers/docker-catalog-page.tsx'
import FlowsPage from '@/app/flows/flows-page.tsx'
import WizardsPage from '@/app/wizards/wizards-page.tsx'
import SettingsView from '@/app/settings/SettingsView.tsx'
import WsChat from '@/app/wschat/WsChat.tsx'
import WizardApp from '@/app/wizards/WizardApp.tsx'
import DeveloperPage from '@/app/developer/developer-page.tsx'
import { AgentsChatsPage } from '@/app/agents/agent-chats-page.tsx'
import SettingsPage from '@/app/settings/SettingsPage.tsx'
import { McpServersView } from '@/app/mcp-servers/mcp-servers-view.tsx'


type Route = {
  path: string;
}

const RouteContext = React.createContext<Route | null>(null)

const AppRouter = () => {

  //const queryParams = new URLSearchParams(window.location.search);
  //const routeQueryPath = queryParams.get('route');
  const [routePath, setRoutePath] = React.useState<string>(window.location.hash.replace('#', '') || '/welcome')

  console.log('>> AppRouter: current URL', window.location.href)
  //const routePath = window.location.hash.replace('#', '')
  console.log('>> AppRouter: current route path', routePath)

  React.useEffect(() => {
    const handleHashChange = () => {
      const newPath = window.location.hash.replace('#', '')
      console.log('>> Hash changed to:', newPath)
      setRoutePath(newPath)
    }

    // Listen for hash changes
    window.addEventListener('hashchange', handleHashChange)

    // Cleanup listener on unmount
    return () => {
      window.removeEventListener('hashchange', handleHashChange)
    }
  }, [])

  const routes = [
    {
      path: '/welcome',
      element: <WelcomeScreen />,
    },
    {
      path: '/chat',
      element: <CompletionChatPage />,
    },
    {
      path: '/agents',
      element: <AgentsChatsPage />,
    },
    {
      path: '/mcp',
      element: <McpServersPage />,
    },
    {
      path: '/mcp/docker',
      element: <DockerCatalogPage />,
    },
    {
      path: '/flows',
      element: <FlowsPage />,
    },
    {
      path: '/wschat',
      element: <WsChat />,
    },
    {
      path: '/wizards',
      element: <WizardsPage />,
    },
    {
      path: '/wizard',
      element: <WizardApp />,
    },
    {
      path: '/dev',
      element: <DeveloperPage />,
    },
    {
      path: '/settings',
      element: <SettingsPage />,
    },
  ]

  const match = React.useMemo(() => {
    return routes.find(v => v.path===routePath)
  }, [routePath, routes])

  const currentView = React.useMemo(() => {
    if (match) {
      return match
    }
    // Fallback to the first route if no match is found
    //return routes[0];
    return {
      path: 'not-found',
      element: <>Not found</>,
    }
  }, [match, routes])

  const currentRoute = React.useMemo(() => {
    return {
      path: routePath,
    }
  }, [routePath])

  if (!currentView) {
    return <div className="text-center text-red-500">View not found: {routePath}</div>
  }

  return <RouteContext.Provider value={currentRoute}>
    {currentView.element}
  </RouteContext.Provider>
}

export const useRoute = () => {
  const route = React.useContext(RouteContext)
  if (!route) {
    throw new Error('useRoute must be used within a RouteContext.Provider')
  }
  return route
}

export const useNavigate = () => {
  const route = React.useContext(RouteContext)
  if (!route) {
    throw new Error('useNavigate must be used within a RouteContext.Provider')
  }

  const navigate = (path: string) => {
    console.log('>> Navigating to:', path)
    window.location.hash = path // Update the URL hash
    // Trigger a re-render of the AppRouter to match the new path
    const event = new HashChangeEvent('hashchange', {
      newURL: window.location.href,
      oldURL: window.location.href,
    })
    window.dispatchEvent(event)
  }

  return navigate
}

export default AppRouter
