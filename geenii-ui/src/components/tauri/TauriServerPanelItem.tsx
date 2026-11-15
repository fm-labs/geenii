import React from 'react'
import { LoaderCircle, Play, RotateCw, Server, Square } from 'lucide-react'
import { cn } from 'cn'
import useNotification from '@/hooks/useNotification.ts'
import { useOptionalDesktop } from './DesktopStartupGate.tsx'
import { describeServerStatus, restartServer, startServer, stopServer } from './desktop-runtime.ts'
import { useTauriPanel } from './TauriPanelContext.tsx'
import DesktopInfoView from './DesktopInfoView.tsx'
import IconButton from './PanelIconButton.tsx'

/** Server status with start / stop buttons for the server the desktop app manages. */
const TauriServerPanelItem = () => {
  const desktop = useOptionalDesktop()
  const notify = useNotification()
  const panel = useTauriPanel()
  const [pending, setPending] = React.useState<'start' | 'stop' | 'restart' | null>(null)

  if (!desktop) return null
  const status = desktop.server.status
  const { label, dot, busy } = describeServerStatus(status)
  // Only a server the app started can be stopped; an external one is left alone.
  const canStop = status?.state === 'ready' && !status.external
  const canStart = !busy && status?.state !== 'ready'

  const toggleInfo = () => {
    if (panel.isOpen) {
      panel.setIsOpen(false)
      panel.setBody(null)
      return
    }
    // A component, not a snapshot: it reads the live status from the desktop context.
    panel.setBody(<DesktopInfoView />)
    panel.setIsOpen(true)
  }

  const actions = { start: startServer, stop: stopServer, restart: restartServer }
  const run = (action: keyof typeof actions) => {
    setPending(action)
    actions[action]()
      .catch((error) => notify.error(`Failed to ${action} server: ${error}`))
      .finally(() => setPending(null))
  }

  // A fragment: the buttons are direct children of the panel row, so its gap applies evenly.
  return (
    <>
      <IconButton title={`${label}. Click for app info.`} onClick={toggleInfo} className={cn(panel.isOpen && 'bg-accent')}>
        <span className="relative inline-flex">
          <Server size={14} />
          <span className={cn('absolute -right-0.5 -bottom-0.5 size-1.5 rounded-full ring-2 ring-background', dot, busy && 'animate-pulse')} />
        </span>
      </IconButton>
      {pending || busy ? (
        <span className="inline-flex size-6 items-center justify-center" aria-label="working">
          <LoaderCircle size={14} className="animate-spin" />
        </span>
      ) : canStop ? (
        <>
          <IconButton title="Stop server" onClick={() => run('stop')}>
            <Square size={14} />
          </IconButton>
          <IconButton title="Restart server" onClick={() => run('restart')}>
            <RotateCw size={14} />
          </IconButton>
        </>
      ) : (
        <IconButton title="Start server" disabled={!canStart} onClick={() => run('start')}>
          <Play size={14} />
        </IconButton>
      )}
    </>
  )
}

export default TauriServerPanelItem
