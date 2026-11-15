import React, { PropsWithChildren } from 'react'
import DesktopLoader from './DesktopLoader.tsx'
import { DesktopStartup, useDesktopStartup } from './use-desktop-startup.ts'

const DesktopContext = React.createContext<DesktopStartup | null>(null)

/** Desktop shell info, live server status and server controls; only inside the desktop app. */
export const useDesktop = (): DesktopStartup => {
  const context = React.useContext(DesktopContext)
  if (!context) throw new Error('useDesktop must be used inside <DesktopStartupGate>')
  return context
}

/** Like `useDesktop()`, but null outside the desktop app (e.g. the web app). */
export const useOptionalDesktop = (): DesktopStartup | null => React.useContext(DesktopContext)

/**
 * Shows the startup loader until Tauri, the server and its API are all up, then renders
 * the app. Once shown, the app stays mounted even if the server goes away later
 * (its state stays available through `useDesktop()`).
 */
const DesktopStartupGate = ({ children }: PropsWithChildren) => {
  const startup = useDesktopStartup()
  const [started, setStarted] = React.useState(false)

  React.useEffect(() => {
    if (startup.ready) setStarted(true)
  }, [startup.ready])

  return (
    <DesktopContext.Provider value={startup}>
      {started ? children : <DesktopLoader startup={startup} />}
    </DesktopContext.Provider>
  )
}

export default DesktopStartupGate
