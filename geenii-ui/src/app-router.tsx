import React from 'react'
import CompletionChatPage from '@/app/chat/completion-chat-page.tsx'
import CompletionsPage from '@/app/completion/completions-page.tsx'
import { NotFoundError } from '@/features/errors/not-found-error.tsx'
import FlowsPage from '@/app/flows/flows-page.tsx'
import AudioPage from '@/app/aiassist/audio-page.tsx'
import ToolsPage from '@/app/tools/tools.page.tsx'
import AgentsPage from '@/app/agents/agents-page.tsx'
import AgentPage from '@/app/agents/agent-page.tsx'
import XchatDemoPage1 from '@/app/xchat/xchat-demo-page-1.tsx'
import CatalogPage from '@/app/catalog/catalog-page.tsx'
import ConsolePage from '@/app/console/console-page.tsx'
import ConfigurePage from '@/app/console/configure-page.tsx'
import SystemPage from '@/app/console/system-page.tsx'



type Route = {
  path: string;
  element: React.ReactNode;
}

type RouteMatch = {
  location: string;
  route: Route | null;
  params?: Record<string, string>;
}

const RouteContext = React.createContext<RouteMatch | null>(null)

const AppRouter = () => {

  //const queryParams = new URLSearchParams(window.location.search);
  //const routeQueryPath = queryParams.get('route');
  const [routePath, setRoutePath] = React.useState<string>(window.location.hash.replace('#', '') || '/')
  //const [routeMatch, setRouteMatch] = React.useState<Route | null>(null)

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

  const routes = React.useMemo(() => {
    const routes: Route[] = [
      {
        path: '/',
        element: <AgentsPage />,
      },
      {
        path: '/chat',
        element: <CompletionChatPage />,
      },
      {
        path: '/completions',
        element: <CompletionsPage />,
      },
      {
        path: '/agents',
        element: <AgentsPage />,
      },
      {
        path: '/agents/:name',
        element: <AgentPage />,
      },
      {
        path: '/flows',
        element: <FlowsPage />,
      },
      {
        path: '/audio',
        element: <AudioPage />,
      },
      {
        path: '/console/catalog/:section',
        element: <CatalogPage />,
      },
      {
        path: '/console/configure/:section',
        element: <ConfigurePage />,
      },
      {
        path: '/console/system/:section',
        element: <SystemPage />,
      },
      {
        path: '/console/playground/completions',
        element: <CompletionChatPage />,
      },
      {
        path: '/console/playground/tools',
        element: <ToolsPage />,
      },
      {
        path: '/console/playground/xchat',
        element: <XchatDemoPage1 />,
      },
      {
        path: '/console',
        element: <ConsolePage />,
      },
    ]
    return routes
  }, [])

  const parseUrl = (url: string) => {
    const [path, queryString] = url.split('?')
    const queryParams = new URLSearchParams(queryString || '')
    return { path, queryParams }
  }

  const pathToRegex = (path: string) => {
    // split path, replace dynamic segments with regex groups, and join back
    const segments = path.split('/').map(segment => {
      if (segment.startsWith(':')) {
        return '([^/]+)' // capture group for dynamic segment
      }
      return segment
    })
    return new RegExp(`^${segments.join('/')}$`)
  }

  const match: RouteMatch = React.useMemo(() => {
    // parse the routePath to handle query parameters if needed
    const [basePath] = routePath.split('?')
    const routePathToMatch = basePath || routePath
    // Find the first route that matches the current path and map dynamic segments
    for (const route of routes) {
      const regex = pathToRegex(route.path)
      const matchResult = regex.exec(routePathToMatch)
      if (matchResult) {
        const paramValues = matchResult.slice(1) // first element is the full match
        const paramNames = (route.path.match(/:([^/]+)/g) || []).map(name => name.substring(1)) // extract param names
        const params: Record<string, string> = {}
        paramNames.forEach((name, index) => {
          params[name] = paramValues[index]
        })
        console.log('>> Matched route:', route.path, 'with params:', params)

        return {
          location: routePath,
          route: route,
          params: params,
        }
      }
    }
    //return routes.find(v => v.path===routePathToMatch)
    return null
  }, [routePath, routes])

  const currentView: Route = React.useMemo(() => {
    if (match) {
      return match.route
    }
    // Fallback to the first route if no match is found
    //return routes[0];
    return {
      path: 'not-found',
      element: <NotFoundError />,
    }
  }, [match])

  // const currentRoute = React.useMemo(() => {
  //   return {
  //     location: routePath,
  //     route: match
  //   }
  // }, [routePath, match])

  if (!currentView) {
    return <div className="text-center text-red-500">View not found: {routePath}</div>
  }

  return <RouteContext.Provider value={match}>
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
