import React from 'react'
import { IAiClient, IDockerApiClient } from '../api/xai.types.ts'
import { initTauriDockerApiClient, initTauriXapi, initWebXapi } from '../init.ts'
import { AppContext } from './AppContext.tsx'
import { FEATURE_TAURI_XAPI_ENABLED } from '../constants.ts'
import TauriWrapper from '../components/tauri/TauriWrapper.tsx'
import { ServerContext } from './ServerContext.tsx'
import { Button } from '@/components/ui/button.tsx'

export const AppContextProvider: React.FC<React.PropsWithChildren> = ({ children }) => {
  // @ts-ignore
  const isTauri = typeof window.__TAURI__!=='undefined'

  const { serverUrl } = React.useContext(ServerContext)

  const [dockerApi, setDockerApi] = React.useState<IDockerApiClient | null>(null)
  const [xaiApi, setXaiApi] = React.useState<IAiClient>(null)

  //const apiBaseUrl = DEFAULT_XAI_API_URL

  const contextValue = React.useMemo(() => {
    return { isTauri, xaiApi, dockerApi }
  }, [xaiApi, dockerApi])

  const [loading, setLoading] = React.useState<boolean>(true)
  const [ready, setReady] = React.useState<boolean>(false)
  const [bootLog, setBootLog] = React.useState<string[]>([])

  const loadXapi = async () => {
    let xapiClient
    try {
      if (isTauri && FEATURE_TAURI_XAPI_ENABLED) {
        xapiClient = await initTauriXapi()
      } else {
        xapiClient = await initWebXapi(serverUrl)
      }
    } catch (error) {
      setBootLog(prev => [...prev, `❌ Error initializing api client: ${error.message}`])
      throw error;
    }

    if (!xapiClient) {
      throw new Error('API client initialization failed.')
    }
    setXaiApi(xapiClient)
    console.log('API client initialized with base url', serverUrl)

    try {
      const apiInfo = await xapiClient.getInfo()
      setBootLog(prev => [...prev, `ℹ️ API Version: ${apiInfo.version}`])
    } catch (error) {
      setBootLog(prev => [...prev, `❌ Error fetching API info: ${error.message}`])
      throw error // Re-throw to handle in the main initialization flow
    }
  }

  const loadDockerApiClient = async () => {
    if (isTauri) {
      try {
        const dockerApiClient = await initTauriDockerApiClient()
        setDockerApi(dockerApiClient)
        setBootLog(prev => [...prev, '✅ Docker MCP API initialized successfully.'])

        // checking docker version
        const dockerVersion = await dockerApiClient.getVersion()
        setBootLog(prev => [...prev, `ℹ️ Docker Version: ${dockerVersion}`])
        if (!dockerVersion) {
          //throw new Error("Docker version is not available.");
          setBootLog(prev => [...prev, '⚠️ WARN: Docker version is not available.'])
        }

        // checking the mcp version
        const mcpVersion = await dockerApiClient.getMcpVersion()
        setBootLog(prev => [...prev, `ℹ️ Docker MCP API Version: ${mcpVersion}`])
        if (!mcpVersion) {
          //throw new Error("Docker MCP API version is not available.");
          setBootLog(prev => [...prev, '⚠️ WARN: Docker MCP API version is not available.'])
        }

        // checking the model version

      } catch (error) {
        setBootLog(prev => [...prev, `❌ Error initializing Docker MCP API: ${error.message}`])
      }
    } else {
      setBootLog(prev => [...prev, 'ℹ️ Docker MCP API is not available in web mode.'])
    }
  }

  const checkApiVersion = async () => {
    try {
      // const response = await fetch('/api/version');
      // if (!response.ok) {
      //     throw new Error('Network response was not ok');
      // }
      // const data = await response.json();
      const data = { version: '1.0.0' } // Mocked API response for demonstration
      setBootLog(prev => [...prev, `ℹ️ API Version: ${data.version}`])
    } catch (error) {
      setBootLog(prev => [...prev, `❌ Error fetching API version: ${error.message}`])
      throw error // Re-throw to handle in the main initialization flow
    }
  }

  const checkUserAgent = async () => {
    const userAgent = navigator.userAgent
    setBootLog(prev => [...prev, `ℹ️ User Agent: ${userAgent}`])
  }

  const checkTimeout = async (timeout: number) => {
    return new Promise((resolve) => {
      setTimeout(() => {
        setBootLog(prev => [...prev, `⚠️ Timeout of ${timeout}ms reached.`])
        resolve(true)
      }, timeout)
    })
  }

  React.useEffect(() => {
    const initialize = async () => {
      setBootLog(['ℹ️ Loading ...'])
      const initResults = await Promise.all([
        //checkApiVersion(),
        checkUserAgent(),
        //checkTimeout(2000),
        loadXapi(),
        //loadDockerApiClient(),
      ]).then(() => {
        setBootLog(prev => [...prev, '✅ All checks completed.'])
        setLoading(false)
        setReady(true)
      }).catch(error => {
        setBootLog(prev => [...prev, `❌ Error during initialization: ${error.message}`])
        //setLoading(false);
        setReady(false)
      })
      console.log(initResults)
    }

    // DISABLED FOR NOW TO SPEED UP LOADING
    const timer = setTimeout(() => {
      initialize().catch(error => {
        setBootLog(prev => [...prev, `❌ Initialization error: ${error.message}`])
        //setLoading(false);
      })
    }, 10) // Delay to prevent double initialization in strict mode

    return () => {
      clearTimeout(timer)
    }
  }, [])

  if (loading || !ready) {
    return (<div className="boot-screen container mx-auto p-4">
      {/*DEV_MODE &&*/ <div className="boot-log mb-4">
        {bootLog.map((log, index) => (
          <div key={index} className="boot-log">
            {log}
          </div>
        ))}
        {!ready && <Button variant={"ghost"} onClick={() => setReady(true)}>Continue</Button>}
      </div>}
    </div>)
  }

  if (isTauri) {
    return (
      <AppContext.Provider value={contextValue}>
        <TauriWrapper>
          {children}
        </TauriWrapper>
      </AppContext.Provider>
    )
  }

  return (
    <AppContext.Provider value={contextValue}>
      {children}
    </AppContext.Provider>
  )
}
