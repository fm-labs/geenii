import React from 'react'
import { CircleCheck, CircleDashed, CircleX, LoaderCircle, Play, RotateCw } from 'lucide-react'
import { Button } from '@/components/ui/button.tsx'
import { cn } from 'cn'
import { APP_NAME } from '@/constants.ts'
import { ServerStatus } from './desktop-runtime.ts'
import { DesktopStartup } from './use-desktop-startup.ts'

type StepState = DesktopStartup['tauri']['state']

const formatBytes = (bytes: number) => {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

const StepIcon = ({ state }: { state: StepState }) => {
  const className = 'size-5 shrink-0'
  switch (state) {
    case 'done':
      return <CircleCheck className={cn(className, 'text-emerald-600 dark:text-emerald-400')} aria-label="done" />
    case 'active':
      return <LoaderCircle className={cn(className, 'animate-spin text-foreground')} aria-label="in progress" />
    case 'error':
      return <CircleX className={cn(className, 'text-destructive')} aria-label="failed" />
    default:
      return <CircleDashed className={cn(className, 'text-muted-foreground/60')} aria-label="pending" />
  }
}

const Step = (props: React.PropsWithChildren<{ state: StepState; title: string }>) => (
  <li className="flex gap-3">
    <StepIcon state={props.state} />
    <div className="min-w-0 flex-1 space-y-1.5">
      <div className={cn('text-sm font-medium leading-5', props.state === 'pending' && 'text-muted-foreground')}>
        {props.title}
      </div>
      {props.children}
    </div>
  </li>
)

const Detail = ({ children, error }: React.PropsWithChildren<{ error?: boolean }>) => (
  <div className={cn('text-xs break-words', error ? 'text-destructive' : 'text-muted-foreground')}>{children}</div>
)

const ProgressBar = ({ value }: { value: number | null }) => (
  <div
    className="h-1.5 w-full overflow-hidden rounded-full bg-muted"
    role="progressbar"
    aria-valuemin={0}
    aria-valuemax={100}
    aria-valuenow={value ?? undefined}
  >
    {value === null ? (
      <div className="h-full w-1/3 animate-pulse rounded-full bg-primary/60" />
    ) : (
      <div className="h-full rounded-full bg-primary transition-[width] duration-200" style={{ width: `${value}%` }} />
    )}
  </div>
)

const ServerDetail = ({ status, version }: { status: ServerStatus | null; version?: string }) => {
  if (!status) return null
  switch (status.state) {
    case 'idle':
    case 'checking':
      return <Detail>Looking for a running server…</Detail>
    case 'downloading': {
      const percent = status.total ? Math.min(100, Math.round((status.downloaded / status.total) * 100)) : null
      return (
        <>
          <Detail>
            Downloading server {version} — {formatBytes(status.downloaded)}
            {status.total ? ` of ${formatBytes(status.total)} (${percent}%)` : ''}
          </Detail>
          <ProgressBar value={percent} />
          <Detail>This only happens on first start or after an update.</Detail>
        </>
      )
    }
    case 'installing':
      return (
        <>
          <Detail>Verifying and unpacking server {version}…</Detail>
          <ProgressBar value={null} />
        </>
      )
    case 'starting':
      return <Detail>Launching server… The first start after an install can take a few seconds.</Detail>
    case 'ready':
      return <Detail>{status.external ? 'Using a server that was already running.' : `Server ${version} is running.`}</Detail>
    case 'disabled':
      return <Detail>Autostart is off (GEENII_DESKTOP_DEV_MODE=true). Start a server yourself, or start it here.</Detail>
    case 'stopped':
      return <Detail error>The server was stopped.</Detail>
    case 'failed':
      return <Detail error>{status.error}</Detail>
  }
}

const DesktopLoader = ({ startup }: { startup: DesktopStartup }) => {
  const { tauri, server, backend } = startup
  const info = tauri.info
  const providers = backend.info?.providers?.filter((p) => p.configured).map((p) => p.name) ?? []
  const showLog = (server.state === 'error' || backend.state === 'error') && info?.serverLog

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4 py-10 text-foreground">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <div className="text-2xl font-semibold tracking-tight">{APP_NAME}</div>
          <div className="mt-1 text-sm text-muted-foreground">
            {startup.ready ? 'Ready' : 'Getting things ready…'}
          </div>
        </div>

        <div className="rounded-xl border bg-card p-6 shadow-sm">
          <ol className="space-y-5">
            <Step state={tauri.state} title="Connect to desktop app">
              {tauri.error && <Detail error>{tauri.error}</Detail>}
              {info && (
                <Detail>
                  {info.appName} {info.appVersion} · Tauri {info.tauriVersion} · {info.os}/{info.arch}
                </Detail>
              )}
              {tauri.state === 'error' && (
                <Button size="sm" variant="outline" onClick={startup.retryConnection}>
                  <RotateCw /> Retry
                </Button>
              )}
            </Step>

            <Step state={server.state} title="Start geenii server">
              <ServerDetail status={server.status} version={info?.serverVersion} />
              {info?.serverBinOverride && server.state !== 'pending' && (
                <Detail>Using local binary {info.serverBinOverride}</Detail>
              )}
              {server.state === 'error' && (
                <Button size="sm" variant="outline" onClick={startup.restartServer}>
                  <RotateCw /> Restart server
                </Button>
              )}
              {server.status?.state === 'disabled' && (
                <Button size="sm" variant="outline" onClick={startup.restartServer}>
                  <Play /> Start server
                </Button>
              )}
            </Step>

            <Step state={backend.state} title="Connect to server API">
              {backend.state === 'active' && <Detail>Waiting for {info?.serverUrl}…</Detail>}
              {backend.state === 'done' && (
                <Detail>
                  geenii {backend.info?.app?.version ?? 'unknown version'} at {info?.serverUrl}
                  {providers.length > 0 && ` · providers: ${providers.join(', ')}`}
                </Detail>
              )}
              {backend.error && (
                <>
                  <Detail error>{info?.serverUrl}: {backend.error}</Detail>
                  <div className="flex gap-2">
                    <Button size="sm" variant="outline" onClick={startup.retryBackend}>
                      <RotateCw /> Retry
                    </Button>
                    <Button size="sm" variant="ghost" onClick={startup.restartServer}>
                      Restart server
                    </Button>
                  </div>
                </>
              )}
            </Step>
          </ol>
        </div>

        {showLog && (
          <div className="mt-4 text-center text-xs text-muted-foreground">
            Server log: <span className="select-all font-mono">{info.serverLog}</span>
          </div>
        )}
      </div>
    </div>
  )
}

export default DesktopLoader
