import React from 'react'
import { ExternalLinkIcon } from 'lucide-react'
import { Badge } from '@/components/ui/badge.tsx'
import { Button } from '@/components/ui/button.tsx'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card.tsx'
import { Skeleton } from '@/components/ui/skeleton.tsx'
import { useNavigate } from '@/app-router.tsx'
import { cn } from 'cn'
import {
  GeeAppInfo, useAppUrl, useApps, useOpenExternal,
} from '@/app/apps/apps-api.ts'
import { AppControls, AppStatusBadge, DaemonNotRunning, fmtUptime, Notice } from '@/app/apps/apps-components.tsx'

const AppCard = ({ app, onDone }: { app: GeeAppInfo, onDone: (message: string, warn?: boolean) => void }) => {
  const navigate = useNavigate()
  const url = useAppUrl(app)
  const openExternal = useOpenExternal()

  return (
    <Card className="gap-3">
      <CardHeader>
        <CardTitle className="flex items-start justify-between gap-2 text-base">
          <button className="min-w-0 truncate text-left hover:underline" onClick={() => navigate(`/apps/${encodeURIComponent(app.name)}`)}>
            {app.title}
          </button>
          <AppStatusBadge app={app} />
        </CardTitle>
        <CardDescription className="flex flex-wrap items-center gap-2 text-xs">
          <Badge variant="outline" className="font-mono">{app.type}</Badge>
          {app.title !== app.name && <span className="font-mono">{app.name}</span>}
          <span>v{app.version}</span>
          {app.autostart && <Badge variant="secondary" title="Started when the daemon starts">autostart</Badge>}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex-1 text-sm">
        <p className={cn('line-clamp-2', !app.description && 'text-muted-foreground')}>
          {app.description || 'No description.'}
        </p>
        {app.status === 'running' && (
          <div className="pt-2 font-mono text-xs text-muted-foreground">
            port {app.port} · up {fmtUptime(app.uptime_s)}
          </div>
        )}
      </CardContent>
      <CardFooter className="flex flex-wrap justify-between gap-2">
        <AppControls app={app} onDone={onDone} />
        <div className="flex gap-2">
          {app.status === 'running' && url && (
            <Button size="sm" variant="ghost" onClick={() => openExternal(url)} title={url}>
              <ExternalLinkIcon /> Browser
            </Button>
          )}
          <Button size="sm" variant="secondary" onClick={() => navigate(`/apps/${encodeURIComponent(app.name)}`)}>
            Open
          </Button>
        </div>
      </CardFooter>
    </Card>
  )
}

const AppsView = () => {
  const { data, error, loading, reload } = useApps()
  const [notice, setNotice] = React.useState<{ text: string, warn?: boolean } | null>(null)

  const onDone = (text: string, warn?: boolean) => {
    setNotice({ text, warn })
    // Show the new state, then (after the spawn or a quick crash) the settled one
    reload(true)
    setTimeout(() => reload(true), 1500)
  }

  const apps = React.useMemo(() => [...(data?.apps ?? [])].sort((a, b) => a.title.localeCompare(b.title)), [data])
  const daemonRunning = !!data?.daemon.running

  return (
    <div className="flex flex-col gap-4">
      <Notice notice={notice} onDismiss={() => setNotice(null)} />

      {error && (
        <div className="rounded-lg border border-destructive/50 p-4 text-sm text-destructive">Failed to load apps: {error}</div>
      )}

      {data && !daemonRunning && <DaemonNotRunning what="apps can't be started" />}

      {!data && loading && (
        <div className="grid gap-4 sm:grid-cols-1 lg:grid-cols-3">
          {[0, 1, 2].map((i) => <Skeleton key={i} className="h-44 rounded-xl" />)}
        </div>
      )}

      {data && apps.length === 0 && (
        <div className="rounded-lg border p-6 text-sm text-muted-foreground">
          No apps yet. Put an app directory into <code className="font-mono">~/.geenii/apps</code> or the
          project&apos;s <code className="font-mono">.geenii/apps</code>, then rescan them in the{' '}
          <a href="#/console/configure/apps" className="underline underline-offset-4 hover:text-foreground">console app settings</a>.
        </div>
      )}

      {apps.length > 0 && (
        <div className={cn('grid gap-4 sm:grid-cols-1 lg:grid-cols-3 transition-opacity', loading && 'opacity-60')}>
          {apps.map((app) => <AppCard key={app.name} app={app} onDone={onDone} />)}
        </div>
      )}
    </div>
  )
}

export default AppsView
