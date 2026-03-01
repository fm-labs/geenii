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

const initXapiClient = async (serverUrl: string): Promise<IAiClient> => {
  if (isTauri && FEATURE_TAURI_XAPI_ENABLED) {
    return await initTauriXapi()
  } else {
    return await initWebXapi(serverUrl)
  }
}


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
    // first load the API client
    const initializeApiClient = async () => {
      setBootLog(['ℹ️ Initializing ...'])
      try {
        await loadXapi()
      } catch (error) {
        setBootLog(prev => [...prev, `❌ Initialization error: ${error.message}`])
      }
    }
    initializeApiClient()
  }, [])

  React.useEffect(() => {
    // then fetch info if client is ready
    if (xaiApi) {
      console.log('API client is ready, fetching info...')
      setBootLog(prev => [...prev, 'ℹ️ API client initialized, fetching info...'])
      fetchInfo().then(setApiInfo).catch(error => {
        console.error(`Error fetching API info: ${error.message}`)
        setApiInfo(null)
      })
    } else {
      console.log('API client is not ready yet.')
    }
  }, [xaiApi])

  React.useEffect(() => {
    // check info every 30 seconds to update the status
    // todo check status enpoint instead
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

  if (!xaiApi || !apiInfo) {
    return (
      <div className='h-svh'>
        <div className='m-auto flex h-full w-full flex-col items-center justify-center gap-2'>
          <h1 className='text-[7rem] leading-tight font-bold'>313</h1>
          <span className='font-medium'>Waiting for geenii</span>
          <p className='text-muted-foreground text-center'>
            Connecting to the geenii engine... <br />
          </p>
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
