import React from 'react'
import { ArrowLeftIcon, ChevronRightIcon, ExternalLinkIcon, RefreshCwIcon } from 'lucide-react'
import MainLayout from '@/components/layout/main-layout.tsx'
import MainContent from '@/components/layout/main-content.tsx'
import { Badge } from '@/components/ui/badge.tsx'
import { Button } from '@/components/ui/button.tsx'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible.tsx'
import { Skeleton } from '@/components/ui/skeleton.tsx'
import { useNavigate, useRoute } from '@/app-router.tsx'
import { cn } from 'cn'
import { GeeAppInfo, useApp, useAppUrl, useOpenExternal } from '@/app/apps/apps-api.ts'
import {
  AppControls, AppLog, AppStatusBadge, DaemonNotRunning, fmtUptime, Notice,
} from '@/app/apps/apps-components.tsx'

const Field = ({ label, children }: { label: string, children: React.ReactNode }) => (
  <div className="grid grid-cols-[8rem_minmax(0,1fr)] gap-3 py-1 text-sm">
    <dt className="text-muted-foreground">{label}</dt>
    <dd className="min-w-0 break-words font-mono text-xs">{children}</dd>
  </div>
)

/** The running app, served by its own process on its port */
const AppFrame = ({ app, url }: { app: GeeAppInfo, url: string }) => {
  // Bumped to reload the frame
  const [frameKey, setFrameKey] = React.useState(0)
  const openExternal = useOpenExternal()

  return (
    <div className="flex flex-col overflow-hidden rounded-lg border">
      <div className="flex items-center justify-between gap-2 border-b bg-muted/40 px-2 py-1">
        <span className="truncate font-mono text-xs text-muted-foreground">{url}</span>
        <div className="flex gap-1">
          <Button size="icon-xs" variant="ghost" title="Reload" onClick={() => setFrameKey((k) => k + 1)}>
            <RefreshCwIcon />
          </Button>
          <Button size="icon-xs" variant="ghost" title="Open in browser" onClick={() => openExternal(url)}>
            <ExternalLinkIcon />
          </Button>
        </div>
      </div>
      <iframe
        key={frameKey}
        title={app.title}
        src={url}
        className="h-[70vh] w-full bg-white"
        // The app is served from its own origin (its port), so same-origin doesn't reach the UI
        sandbox="allow-scripts allow-same-origin allow-forms allow-modals allow-downloads allow-popups"
        allow="microphone"
        referrerPolicy="no-referrer"
      />
    </div>
  )
}

const AppPlaceholder = ({ app }: { app: GeeAppInfo }) => {
  let text: string
  if (app.status === 'starting') text = 'The app is starting…'
  else if (app.status === 'error') text = 'The app keeps failing; check its log below.'
  else if (app.status === 'stopped') text = 'The app is stopped. Start it to use it here.'
  else text = 'The app runs once the geenii daemon is running.'
  return (
    <div className="flex h-64 items-center justify-center rounded-lg border border-dashed text-sm text-muted-foreground">
      {text}
    </div>
  )
}

const AppDetails = ({ app }: { app: GeeAppInfo }) => (
  <dl>
    <Field label="Type">{app.type}</Field>
    <Field label="Version">{app.version}</Field>
    <Field label="Path">{app.path}</Field>
    <Field label="Port">{app.port ?? 'assigned at start'}</Field>
    <Field label="Service">{app.service}</Field>
    {app.pid && <Field label="PID">{app.pid}</Field>}
    {app.status === 'running' && <Field label="Uptime">{fmtUptime(app.uptime_s)}</Field>}
    {app.failures > 0 && <Field label="Failures"><span className="text-amber-600">{app.failures} in a row</span></Field>}
    {app.last_exit && (
      <Field label="Last exit">
        rc={app.last_exit.returncode} at {new Date(app.last_exit.exited_at * 1000).toLocaleString()}
      </Field>
    )}
    <Field label="Enabled">{app.enabled ? 'yes' : 'no (change it in the console app settings)'}</Field>
    <Field label="Autostart">{app.autostart ? 'yes, when the daemon starts or discovers the app' : 'no'}</Field>
    <Field label="Trusted">{app.trusted ? 'yes' : 'no'}</Field>
  </dl>
)

const AppPage = () => {
  const route = useRoute()
  const navigate = useNavigate()
  const name = route?.params?.appId ? decodeURIComponent(route.params.appId) : null
  const { data: app, error, loading, reload } = useApp(name)
  const url = useAppUrl(app)
  const [notice, setNotice] = React.useState<{ text: string, warn?: boolean } | null>(null)
  const [logOpen, setLogOpen] = React.useState(false)

  const onDone = (text: string, warn?: boolean) => {
    setNotice({ text, warn })
    // Show the new state, then (after the spawn or a quick crash) the settled one
    reload(true)
    setTimeout(() => reload(true), 1500)
  }

  // Open the log when the app fails, so the cause is visible
  React.useEffect(() => {
    if (app?.status === 'error') setLogOpen(true)
  }, [app?.status])

  return (
    <MainLayout>
      <MainContent>
        <div className="flex flex-col gap-4">
          <div>
            <Button size="sm" variant="ghost" className="-ml-2 text-muted-foreground" onClick={() => navigate('/apps')}>
              <ArrowLeftIcon /> Apps
            </Button>
          </div>

          {error && (
            <div className="rounded-lg border border-destructive/50 p-4 text-sm text-destructive">
              Failed to load app &quot;{name}&quot;: {error}
            </div>
          )}

          {!app && loading && <Skeleton className="h-96 rounded-xl" />}

          {app && (
            <>
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="min-w-0">
                  <h1 className="flex items-center gap-3 text-2xl font-bold tracking-tight">
                    <span className="truncate">{app.title}</span>
                    <AppStatusBadge app={app} />
                  </h1>
                  <div className="flex flex-wrap items-center gap-2 pt-1 text-sm text-muted-foreground">
                    <Badge variant="outline" className="font-mono">{app.type}</Badge>
                    {app.title !== app.name && <span className="font-mono text-xs">{app.name}</span>}
                    {app.autostart && <Badge variant="secondary" title="Started when the daemon starts">autostart</Badge>}
                    {app.description && <span>{app.description}</span>}
                  </div>
                </div>
                <AppControls app={app} onDone={onDone} />
              </div>

              <Notice notice={notice} onDismiss={() => setNotice(null)} />
              {app.status === null && <DaemonNotRunning what="the app can't run" />}

              {app.status === 'running' && url ? <AppFrame app={app} url={url} /> : <AppPlaceholder app={app} />}

              <Collapsible open={logOpen} onOpenChange={setLogOpen} className="rounded-lg border">
                <CollapsibleTrigger asChild>
                  <button className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm font-medium hover:bg-muted/50">
                    <ChevronRightIcon className={cn('size-4 text-muted-foreground transition-transform', logOpen && 'rotate-90')} />
                    Log
                  </button>
                </CollapsibleTrigger>
                <CollapsibleContent className="px-3 pb-3">
                  {logOpen && (app.status !== null
                    ? <AppLog name={app.name} />
                    : <div className="text-xs text-muted-foreground">The log is kept by the daemon.</div>)}
                </CollapsibleContent>
              </Collapsible>

              <Collapsible className="rounded-lg border">
                <CollapsibleTrigger asChild>
                  <button className="group flex w-full items-center gap-2 px-3 py-2 text-left text-sm font-medium hover:bg-muted/50">
                    <ChevronRightIcon className="size-4 text-muted-foreground transition-transform group-data-[state=open]:rotate-90" />
                    Details
                  </button>
                </CollapsibleTrigger>
                <CollapsibleContent className="px-3 pb-3">
                  <AppDetails app={app} />
                </CollapsibleContent>
              </Collapsible>
            </>
          )}
        </div>
      </MainContent>
    </MainLayout>
  )
}

export default AppPage
