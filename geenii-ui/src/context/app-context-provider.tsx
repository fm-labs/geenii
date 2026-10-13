import React from 'react'
import { AppContext } from './app-context.tsx'
import { XAI_API_INFO_CHECK_INTERVAL_MS } from '../constants.ts'
import TauriWrapper from '../components/tauri/TauriWrapper.tsx'
import { ApiContext } from '@/context/api-context.tsx'

// @ts-ignore
const isTauri = typeof window.__TAURI__!=='undefined'

const BOOT_LOG_MAX_LINES = 20

export const AppContextProvider: React.FC<React.PropsWithChildren> = ({ children }) => {

  const { api } = React.useContext(ApiContext)

  const [apiInfo, setApiInfo] = React.useState<any>(null)

  const contextValue = React.useMemo(() => {
    return { isTauri, apiInfo }
  }, [apiInfo])

  //const [loading, setLoading] = React.useState<boolean>(true)
  //const [ready, setReady] = React.useState<boolean>(false)
  const [bootLog, setBootLog] = React.useState<string[]>([])

  // the info poll repeats the same lines every interval: skip repeats and keep only the latest entries
  const log = React.useCallback((line: string) => {
    setBootLog(prev => prev[prev.length - 1] === line ? prev : [...prev, line].slice(-BOOT_LOG_MAX_LINES))
  }, [])

  const fetchInfo = React.useCallback(async () => {
    console.log('fetch info')
    try {
      if (!api) {
        throw new Error('API client is not initialized.')
      }
      const apiInfo = await api.getInfo()
      log(`ℹ️ API Version: ${apiInfo.version}`)
      return apiInfo
    } catch (error) {
      log(`❌ No connection: ${error.message}`)
      throw error // Re-throw to handle in the main initialization flow
    }
  }, [api, log])

  // React.useEffect(() => {
  //   // first load the API client
  //   const initializeApiClient = async () => {
  //     setBootLog(['ℹ️ Initializing ...'])
  //     try {
  //       await loadXapi()
  //     } catch (error) {
  //       setBootLog(prev => [...prev, `❌ Initialization error: ${error.message}`])
  //     }
  //   }
  //   initializeApiClient()
  // }, [])

  React.useEffect(() => {
    // then fetch info if client is ready
    if (api) {
      console.log('API client is ready, fetching info...')
      log('ℹ️ API client initialized, fetching info...')
      fetchInfo().then(setApiInfo).catch(error => {
        console.error(`Error fetching API info: ${error.message}`)
        setApiInfo(null)
      })
    } else {
      console.log('API client is not ready yet.')
    }
  }, [api])

  React.useEffect(() => {
    // check info every 30 seconds to update the status
    // todo check status enpoint instead
    console.log('setting up info fetch interval')
    const interval = setInterval(() => {
      fetchInfo().then(setApiInfo).catch(error => {
        console.error(`Error fetching API info: ${error.message}`)
        setApiInfo(null)
      })
    }, XAI_API_INFO_CHECK_INTERVAL_MS)

    return () => {
      console.log("clearing info fetch interval")
      clearInterval(interval)
    }
  }, [fetchInfo])

  if (!api || !apiInfo) {
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
