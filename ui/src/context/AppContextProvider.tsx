import React from 'react'
import { IAiClient, IDockerApiClient } from '../api/xai.types.ts'
import { initTauriDockerApiClient, initTauriXapi, initWebXapi } from '../init.ts'
import { AppContext } from './AppContext.tsx'
import { FEATURE_TAURI_XAPI_ENABLED } from '../constants.ts'
import TauriWrapper from '../components/tauri/TauriWrapper.tsx'
import { ServerContext } from './ServerContext.tsx'
import { Button } from '@/components/ui/button.tsx'

// @ts-ignore
const isTauri = typeof window.__TAURI__!=='undefined'

export const AppContextProvider: React.FC<React.PropsWithChildren> = ({ children }) => {

  const { serverUrl } = React.useContext(ServerContext)

  const [dockerApi, setDockerApi] = React.useState<IDockerApiClient | null>(null)
  const [xaiApi, setXaiApi] = React.useState<IAiClient>(null)

  //const apiBaseUrl = DEFAULT_XAI_API_URL

  const [apiInfo, setApiInfo] = React.useState<any>(null)

  const contextValue = React.useMemo(() => {
    return { isTauri, xaiApi, dockerApi, apiInfo }
  }, [xaiApi, dockerApi, apiInfo])

  const [loading, setLoading] = React.useState<boolean>(true)
  const [ready, setReady] = React.useState<boolean>(false)
  const [bootLog, setBootLog] = React.useState<string[]>([])

  const loadXapi = React.useCallback(async () => {
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
  }, [isTauri, serverUrl])

  const fetchInfo = React.useCallback(async () => {
    console.log('fetch info')
    try {
      if (!xaiApi) {
        throw new Error('API client is not initialized.')
      }
      const apiInfo = await xaiApi.getInfo()
      setBootLog(prev => [...prev, `ℹ️ API Version: ${apiInfo.version}`])
      return apiInfo
    } catch (error) {
      setBootLog(prev => [...prev, `❌ No connection: ${error.message}`])
      throw error // Re-throw to handle in the main initialization flow
    }
  }, [xaiApi])

  React.useEffect(() => {
    const initialize = async () => {
      setBootLog(['ℹ️ Loading ...'])
      try {
        await loadXapi()
        const info = await fetchInfo()
        setApiInfo(info)
        setBootLog(prev => [...prev, '✅ API client initialized successfully.'])
      } catch (error) {
        setBootLog(prev => [...prev, `❌ Initialization error: ${error.message}`])
      } finally {
      }
    }
    initialize()

    // const timer = setTimeout(() => {
    //   fetchInfo()
    // }, 3000) // Delay to prevent double initialization in strict mode
    //
    // return () => {
    //   clearTimeout(timer)
    // }
  }, [])

  React.useEffect(() => {
    // check info every 30 seconds to update the status
    console.log('setting up info fetch interval')
    const interval = setInterval(() => {
      setBootLog([])
      fetchInfo().then(setApiInfo).catch(error => {
        console.error(`Error fetching API info: ${error.message}`)
        setApiInfo(null)
      })
    }, 10000)

    return () => {
      console.log("clearing info fetch interval")
      clearInterval(interval)
    }
  }, [fetchInfo])

  // const fetchInfoWithRetry = async (retries: number, delay: number) => {
  //   for (let i = 0; i < retries; i++) {
  //     try {
  //       const info = await fetchInfo()
  //       setApiInfo(info)
  //       return // Exit if successful
  //     } catch (error) {
  //       if (i < retries - 1) {
  //         setBootLog(prev => [...prev, `⚠️ Retry ${i + 1} after error: ${error.message}`])
  //         await new Promise(res => setTimeout(res, delay)) // Wait before retrying
  //       } else {
  //         setBootLog(prev => [...prev, `❌ All retries failed: ${error.message}`])
  //         throw error // Re-throw after final attempt
  //       }
  //     }
  //   }
  // }

  //await fetchInfoWithRetry(10, 3000) // Retry up to 10 times with a 3-second delay
  // const loadDockerApiClient = async () => {
  //   if (isTauri) {
  //     try {
  //       const dockerApiClient = await initTauriDockerApiClient()
  //       setDockerApi(dockerApiClient)
  //       setBootLog(prev => [...prev, '✅ Docker API client initialized successfully.'])
  //
  //       // checking docker version
  //       const dockerVersion = await dockerApiClient.getVersion()
  //       setBootLog(prev => [...prev, `ℹ️ Docker Version: ${dockerVersion}`])
  //       if (!dockerVersion) {
  //         //throw new Error("Docker version is not available.");
  //         setBootLog(prev => [...prev, '⚠️ WARN: Docker version is not available.'])
  //       }
  //
  //       // checking the mcp version
  //       const mcpVersion = await dockerApiClient.getMcpVersion()
  //       setBootLog(prev => [...prev, `ℹ️ Docker MCP API Version: ${mcpVersion}`])
  //       if (!mcpVersion) {
  //         //throw new Error("Docker MCP API version is not available.");
  //         setBootLog(prev => [...prev, '⚠️ WARN: Docker MCP API version is not available.'])
  //       }
  //
  //       // checking the model version
  //
  //     } catch (error) {
  //       setBootLog(prev => [...prev, `❌ Error initializing Docker MCP API: ${error.message}`])
  //     }
  //   } else {
  //     setBootLog(prev => [...prev, 'ℹ️ Docker MCP API is not available in web mode.'])
  //   }
  // // }
  //
  // const checkApiVersion = async () => {
  //   try {
  //     // const response = await fetch('/api/version');
  //     // if (!response.ok) {
  //     //     throw new Error('Network response was not ok');
  //     // }
  //     // const data = await response.json();
  //     const data = { version: '1.0.0' } // Mocked API response for demonstration
  //     setBootLog(prev => [...prev, `ℹ️ API Version: ${data.version}`])
  //   } catch (error) {
  //     setBootLog(prev => [...prev, `❌ Error fetching API version: ${error.message}`])
  //     throw error // Re-throw to handle in the main initialization flow
  //   }
  // }
  //
  // const checkUserAgent = async () => {
  //   const userAgent = navigator.userAgent
  //   setBootLog(prev => [...prev, `ℹ️ User Agent: ${userAgent}`])
  // }
  //
  // const checkTimeout = async (timeout: number) => {
  //   return new Promise((resolve) => {
  //     setTimeout(() => {
  //       setBootLog(prev => [...prev, `⚠️ Timeout of ${timeout}ms reached.`])
  //       resolve(true)
  //     }, timeout)
  //   })
  // }
  //
  // React.useEffect(() => {
  //   const initialize = async () => {
  //     setBootLog(['ℹ️ Loading ...'])
  //     const initResults = await Promise.all([
  //       //checkApiVersion(),
  //       //checkUserAgent(),
  //       //checkTimeout(2000),
  //       loadXapi(),
  //       //loadDockerApiClient(),
  //     ]).then(() => {
  //       setBootLog(prev => [...prev, '✅ All checks completed.'])
  //       setLoading(false)
  //       setReady(true)
  //     }).catch(error => {
  //       setBootLog(prev => [...prev, `❌ Error during initialization: ${error.message}`])
  //       //setLoading(false);
  //       setReady(false)
  //     })
  //     console.log(initResults)
  //   }
  //
  //   // DISABLED FOR NOW TO SPEED UP LOADING
  //   const timer = setTimeout(() => {
  //     initialize().catch(error => {
  //       setBootLog(prev => [...prev, `❌ Initialization error: ${error.message}`])
  //       //setLoading(false);
  //     })
  //   }, 10) // Delay to prevent double initialization in strict mode
  //
  //   return () => {
  //     clearTimeout(timer)
  //   }
  // }, [])
  //
  // if (loading || !ready) {
  //   return (<div className="boot-screen container mx-auto p-4">
  //     {/*DEV_MODE &&*/ <div className="boot-log mb-4">
  //       {bootLog.map((log, index) => (
  //         <div key={index} className="boot-log">
  //           {log}
  //         </div>
  //       ))}
  //       {!ready && <Button variant={"ghost"} onClick={() => setReady(true)}>Continue</Button>}
  //     </div>}
  //   </div>)
  // }

  if (!xaiApi || !apiInfo) {
    return (
      <div className='h-svh'>
        <div className='m-auto flex h-full w-full flex-col items-center justify-center gap-2'>
          <h1 className='text-[7rem] leading-tight font-bold'>313</h1>
          <span className='font-medium'>Waiting for geenii</span>
          <p className='text-muted-foreground text-center'>
            Connecting to the geenii engine... <br />
          </p>
          {/*<div className='mt-6 flex gap-4'>
            <Button variant='outline'>Learn more</Button>
          </div>*/}
          <div>
            {bootLog.map((log, index) => (
              <div key={index} className="boot-log">
                {log}
              </div>
            ))}
          </div>
        </div>
      </div>
    )
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
