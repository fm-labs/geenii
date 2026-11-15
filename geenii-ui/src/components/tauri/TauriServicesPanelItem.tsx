import { Server } from 'lucide-react'
import { cn } from 'cn'
import { useOptionalDesktop } from './DesktopStartupGate.tsx'
import { describeServiceStatus, ServiceName, ServiceStatus } from './desktop-runtime.ts'
import { useTauriPanel } from './TauriPanelContext.tsx'
import DesktopInfoView from './DesktopInfoView.tsx'
import IconButton from './PanelIconButton.tsx'

const SERVICES: ServiceName[] = ['server', 'daemon']

/** One indicator for all services: the most urgent state wins. */
function combinedDot(statuses: (ServiceStatus | null)[]): { dot: string; busy: boolean } {
  const states = statuses.map((s) => s?.state)
  if (states.includes('failed')) return { dot: 'bg-destructive', busy: false }
  const busy = statuses.some((s, i) => describeServiceStatus(s, SERVICES[i]).busy)
  if (busy) return { dot: 'bg-amber-500', busy: true }
  if (states.every((s) => s === 'ready')) return { dot: 'bg-emerald-500', busy: false }
  // Some running, some stopped / not started.
  if (states.includes('ready')) return { dot: 'bg-amber-500', busy: false }
  return { dot: 'bg-muted-foreground', busy: false }
}

/**
 * Status icon for the background services the desktop app manages (server and daemon).
 * Opens the info popup, which has each service's details and start / stop / restart controls.
 */
const TauriServicesPanelItem = () => {
  const desktop = useOptionalDesktop()
  const panel = useTauriPanel()

  if (!desktop) return null
  const statuses = [desktop.server.status, desktop.daemon.status]
  const { dot, busy } = combinedDot(statuses)
  const title = statuses.map((s, i) => describeServiceStatus(s, SERVICES[i]).label).join(' · ')

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

  return (
    <IconButton title={`${title}. Click for details and controls.`} onClick={toggleInfo} className={cn(panel.isOpen && 'bg-accent')}>
      <span className="relative inline-flex">
        <Server size={14} />
        <span className={cn('absolute -right-0.5 -bottom-0.5 size-1.5 rounded-full ring-2 ring-background', dot, busy && 'animate-pulse')} />
      </span>
    </IconButton>
  )
}

export default TauriServicesPanelItem
