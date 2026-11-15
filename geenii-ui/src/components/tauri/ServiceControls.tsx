import React from 'react'
import { LoaderCircle, Play, RotateCw, Square } from 'lucide-react'
import { Button } from '@/components/ui/button.tsx'
import useNotification from '@/hooks/useNotification.ts'
import {
  describeServiceStatus,
  restartService,
  SERVICE_LABELS,
  ServiceName,
  ServiceStatus,
  startService,
  stopService,
} from './desktop-runtime.ts'

const ACTIONS = { start: startService, stop: stopService, restart: restartService }
type Action = keyof typeof ACTIONS

/** Start / stop / restart buttons for a service the desktop app manages. */
const ServiceControls = ({ service, status }: { service: ServiceName; status: ServiceStatus | null }) => {
  const notify = useNotification()
  const [pending, setPending] = React.useState<Action | null>(null)
  const { busy } = describeServiceStatus(status, service)
  const noun = SERVICE_LABELS[service].toLowerCase()
  const ready = status?.state === 'ready'
  // Only an instance the app started can be stopped; an external one is left alone.
  const canStop = ready && !status.external
  const working = pending !== null || busy

  const run = (action: Action) => {
    setPending(action)
    ACTIONS[action](service)
      .catch((error) => notify.error(`Failed to ${action} ${noun}: ${error}`))
      .finally(() => setPending(null))
  }

  const icon = (action: Action, Icon: typeof Play) =>
    pending === action ? <LoaderCircle className="animate-spin" /> : <Icon />

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {!ready && (
        <Button size="xs" variant="outline" disabled={working} onClick={() => run('start')} title={`Start ${noun}`}>
          {icon('start', Play)} Start
        </Button>
      )}
      {canStop && (
        <>
          <Button size="xs" variant="outline" disabled={working} onClick={() => run('stop')} title={`Stop ${noun}`}>
            {icon('stop', Square)} Stop
          </Button>
          <Button size="xs" variant="outline" disabled={working} onClick={() => run('restart')} title={`Restart ${noun}`}>
            {icon('restart', RotateCw)} Restart
          </Button>
        </>
      )}
      {ready && !canStop && (
        <span className="text-xs text-muted-foreground">Started outside the app; not managed here.</span>
      )}
      {busy && !pending && <LoaderCircle className="size-3 animate-spin text-muted-foreground" aria-label="working" />}
    </div>
  )
}

export default ServiceControls
