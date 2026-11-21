import React from 'react'
import {
  DownloadIcon, FolderSyncIcon, LoaderIcon, PlusIcon, RefreshCwIcon, SearchIcon, SettingsIcon, Trash2Icon, XIcon,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge.tsx'
import { Button } from '@/components/ui/button.tsx'
import {
  Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from '@/components/ui/dialog.tsx'
import { useNavigate } from '@/app-router.tsx'
import {
  GeeAppInfo, matchesAppQuery, requestError, useAddApp, useAppIconUrl, useApps, useSetAppSetting,
} from '@/app/apps/apps-api.ts'
import { Input } from '@/components/ui/input.tsx'
import { Label } from '@/components/ui/label.tsx'
import { cn } from 'cn'
import MarketplaceView, { MARKETPLACE_COUNT } from '@/app/apps/marketplace-view.tsx'
import { FEATURE_APPS_MARKETPLACE } from '@/constants.ts'
import { useApi } from '@/context/api-context.tsx'
import {
  AppControls, AppSettingToggle, AppStatusBadge, AppStatusDot, DaemonNotRunning, fmtUptime, Notice,
} from '@/app/apps/apps-components.tsx'

const Code = ({ children }: React.PropsWithChildren) => <code className="rounded bg-muted px-1 py-0.5 font-mono text-xs">{children}</code>

/** Add an app directory by its path (it needs a manifest.json; added disabled), or how to drop one into an app directory */
const AddAppDialog = ({ daemonRunning, onAdded }: {
  daemonRunning: boolean
  onAdded: (app: GeeAppInfo) => void
}) => {
  const addApp = useAddApp()
  const [open, setOpen] = React.useState(false)
  const [path, setPath] = React.useState('')
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const onOpenChange = (next: boolean) => {
    setOpen(next)
    if (!next) {
      setPath('')
      setError(null)
    }
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const app = await addApp(path.trim())
      onOpenChange(false)
      onAdded(app)
    } catch (err) {
      setError(requestError(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogTrigger asChild>
        <Button size="sm"><PlusIcon /> Add App</Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Add an app</DialogTitle>
          <DialogDescription>An app is a directory that geenii serves or runs as a background service.</DialogDescription>
        </DialogHeader>

        <form onSubmit={submit} className="flex flex-col gap-2">
          <Label htmlFor="add-app-path">App directory</Label>
          <div className="flex gap-2">
            <Input
              id="add-app-path"
              value={path}
              onChange={(e) => setPath(e.target.value)}
              placeholder="/path/to/my-app"
              className="font-mono"
              autoFocus
              disabled={!daemonRunning}
            />
            <Button type="submit" disabled={!daemonRunning || busy || !path.trim()}>
              {busy && <LoaderIcon className="animate-spin" />} Add
            </Button>
          </div>
          {error
            ? <p className="text-sm text-destructive">{error}</p>
            : (
              <p className="text-xs text-muted-foreground">
                {daemonRunning
                  ? <>An absolute path to a directory with a valid <Code>manifest.json</Code>. The app is added disabled, under Available.</>
                  : 'The geenii daemon is not running, so apps can\'t be added.'}
              </p>
            )}
        </form>

        <div className="flex flex-col gap-2 border-t pt-4 text-sm text-muted-foreground">
          <p>
            Or copy the app directory into <Code>~/.geenii/apps/</Code> (for all projects) or the
            project&apos;s <Code>.geenii/apps/</Code> and click <strong>Rescan</strong>. There a manifest is optional:
            without one, the type is detected from the files (<Code>geenii apps init &lt;name&gt;</Code> writes it).
          </p>
        </div>

        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline">Close</Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

type AppsTab = 'installed' | 'available' | 'marketplace'

const ALL_TABS: { id: AppsTab, label: string, title: string }[] = [
  { id: 'installed', label: 'Installed', title: 'Enabled apps: they can be started and autostarted' },
  { id: 'available', label: 'Available', title: 'Apps found in the app directories that are not enabled' },
  { id: 'marketplace', label: 'Marketplace', title: 'Apps from the app catalog' },
]

const TABS = ALL_TABS.filter(({ id }) => id !== 'marketplace' || FEATURE_APPS_MARKETPLACE)

/**
 * Install (enable) or uninstall (disable and stop) an app; the app's files stay where they are.
 * After an install, it opens the app page.
 */
const InstallButton = ({ app, daemonRunning, onDone }: {
  app: GeeAppInfo
  daemonRunning: boolean
  onDone: (message: string, warn?: boolean) => void
}) => {
  const navigate = useNavigate()
  const setAppSetting = useSetAppSetting()
  const [busy, setBusy] = React.useState(false)
  const install = !app.enabled

  const run = async () => {
    setBusy(true)
    try {
      await setAppSetting(app.name, 'enabled', install)
      if (install) {
        navigate(`/apps/${encodeURIComponent(app.name)}`)
      } else {
        onDone(`Uninstalled "${app.title}"; it is stopped and listed under Available.`)
      }
    } catch (err) {
      onDone(`Could not ${install ? 'install' : 'uninstall'} "${app.title}": ${requestError(err)}`, true)
    } finally {
      setBusy(false)
    }
  }

  const title = !daemonRunning ? 'The geenii daemon is not running'
    : install ? 'Enable the app' : 'Disable the app and stop it if it runs; its files are kept'
  return (
    <span title={title}>
      <Button size="sm" variant={install ? 'default' : 'outline'} onClick={run} disabled={!daemonRunning || busy}>
        {busy ? <LoaderIcon className="animate-spin" /> : install ? <DownloadIcon /> : <Trash2Icon />}
        {install ? 'Install' : 'Uninstall'}
      </Button>
    </span>
  )
}

const InfoRow = ({ label, children }: React.PropsWithChildren<{ label: string }>) => (
  <>
    <dt className="text-muted-foreground">{label}</dt>
    <dd className="min-w-0 break-all">{children}</dd>
  </>
)

/** Everything about one app: info, status and controls, settings, install/uninstall */
const AppSettingsDialog = ({ app, daemonRunning, onDone }: {
  app: GeeAppInfo
  daemonRunning: boolean
  onDone: (message: string, warn?: boolean) => void
}) => {
  // The page's notice is hidden behind the dialog, so the dialog shows the outcome too
  const [notice, setNotice] = React.useState<{ text: string, warn?: boolean } | null>(null)
  const done = (text: string, warn?: boolean) => {
    setNotice({ text, warn })
    onDone(text, warn)
  }

  return (
    <Dialog onOpenChange={(open) => !open && setNotice(null)}>
      <DialogTrigger asChild>
        <Button size="icon" variant="ghost" title="App settings" aria-label={`Settings of ${app.title}`}>
          <SettingsIcon />
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {app.enabled && <AppStatusDot app={app} className="size-3" />}
            {app.title}
            {app.enabled && <AppStatusBadge app={app} />}
          </DialogTitle>
          <DialogDescription>{app.description || 'No description available'}</DialogDescription>
        </DialogHeader>

        <Notice notice={notice} onDismiss={() => setNotice(null)} />

        <dl className="grid grid-cols-[6rem_1fr] gap-x-3 gap-y-1.5 text-sm">
          <InfoRow label="Name"><span className="font-mono">{app.name}</span></InfoRow>
          <InfoRow label="Type"><Badge variant="outline" className="font-mono">{app.type}</Badge></InfoRow>
          <InfoRow label="Version">{app.version}</InfoRow>
          <InfoRow label="Path"><span className="font-mono text-xs">{app.path}</span></InfoRow>
          <InfoRow label="Source">{app.added ? 'Added by path' : 'App directory'}</InfoRow>
          {app.enabled && <InfoRow label="Service"><span className="font-mono text-xs">{app.service}</span></InfoRow>}
          {app.port && <InfoRow label="Port"><span className="font-mono">{app.port}</span></InfoRow>}
          {app.status === 'running' && (
            <InfoRow label="Process">pid <span className="font-mono">{app.pid}</span> · up {fmtUptime(app.uptime_s)}</InfoRow>
          )}
          {app.last_exit && (
            <InfoRow label="Last exit">
              code {app.last_exit.returncode} at {new Date(app.last_exit.exited_at * 1000).toLocaleString()}
            </InfoRow>
          )}
        </dl>

        {app.enabled && (
          <div className="flex flex-col gap-3 border-t pt-4">
            <AppControls app={app} onDone={done} />
            <AppSettingToggle app={app} setting="autostart" onDone={done} />
          </div>
        )}

        <DialogFooter className="border-t pt-4 sm:justify-between">
          <InstallButton app={app} daemonRunning={daemonRunning} onDone={done} />
          <DialogClose asChild>
            <Button size="sm" variant="outline">Close</Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/** A grid card for one app: icon, title, status and description, install and settings */
const AppCard = ({ app, daemonRunning, onDone }: {
  app: GeeAppInfo
  daemonRunning: boolean
  onDone: (message: string, warn?: boolean) => void
}) => {
  const navigate = useNavigate()
  const iconUrl = useAppIconUrl(app.name)
  const open = () => navigate(`/apps/${encodeURIComponent(app.name)}`)
  return (
    <div className="app-card flex flex-col gap-3 rounded-lg border p-4">
      <div className="flex items-start gap-3">
        <button type="button" title="Open the app" onClick={open}
                className={cn('relative flex size-12 shrink-0 items-center justify-center rounded-xl border bg-card p-2',
                  !app.enabled && 'opacity-50 grayscale')}>
          <img src={iconUrl} alt="" className="size-full object-contain" draggable={false} />
          {app.enabled && <AppStatusDot app={app} className="absolute -top-0.5 -right-0.5 size-3 ring-2 ring-background" />}
        </button>
        <div className="min-w-0 flex-1">
          <h3 className="flex items-center gap-2 font-bold">
            <button type="button" className="min-w-0 truncate text-left hover:underline" title="Open the app" onClick={open}>
              {app.title}
            </button>
          </h3>
          <div className="flex flex-wrap items-center gap-1.5 pt-0.5 text-xs text-muted-foreground">
            <Badge variant="outline" className="font-mono">{app.type}</Badge>
            <span>v{app.version}</span>
            {app.enabled && <AppStatusBadge app={app} />}
          </div>
        </div>
        <AppSettingsDialog app={app} daemonRunning={daemonRunning} onDone={onDone} />
      </div>
      <p className={cn('line-clamp-2 flex-1 text-sm', !app.description && 'text-muted-foreground')}>
        {app.description || 'No description available'}
      </p>
      {!app.enabled && (
        <div className="flex justify-end">
          <InstallButton app={app} daemonRunning={daemonRunning} onDone={onDone} />
        </div>
      )}
    </div>
  )
}

const AppsSettings = () => {
  const { fetchJson } = useApi()
  const [tab, setTab] = React.useState<AppsTab>('installed')
  const { data, error, loading, reload } = useApps()
  const [notice, setNotice] = React.useState<{ text: string, warn?: boolean } | null>(null)
  const [rescanning, setRescanning] = React.useState(false)
  const [query, setQuery] = React.useState('')
  const daemonRunning = !!data?.daemon.running

  const apps = React.useMemo(() => [...(data?.apps ?? [])].sort((a, b) => a.title.localeCompare(b.title)), [data])
  const byTab: Record<Exclude<AppsTab, 'marketplace'>, GeeAppInfo[]> = {
    installed: apps.filter((a) => a.enabled),
    available: apps.filter((a) => !a.enabled),
  }
  const counts: Record<AppsTab, number> = {
    installed: byTab.installed.length, available: byTab.available.length, marketplace: MARKETPLACE_COUNT,
  }
  const shown = tab === 'marketplace' ? [] : byTab[tab].filter((a) => matchesAppQuery(a, query))

  const onDone = (text: string, warn?: boolean) => {
    setNotice({ text, warn })
    // Show the new state, then (after a start's spawn or a quick crash) the settled one
    reload(true)
    setTimeout(() => reload(true), 1500)
  }

  const rescan = async () => {
    setRescanning(true)
    try {
      const res = await fetchJson('/api/v1/apps/reload', { method: 'POST' })
      const changes = [
        res.added.length ? `added ${res.added.join(', ')}` : '',
        res.removed.length ? `removed ${res.removed.join(', ')}` : '',
        res.autostarted?.length ? `autostarted ${res.autostarted.join(', ')}` : '',
      ].filter(Boolean).join('; ')
      setNotice({ text: `Rescanned ${res.dirs.length} app director${res.dirs.length === 1 ? 'y' : 'ies'}${changes ? `: ${changes}` : ', no changes'}.` })
    } catch (err) {
      setNotice({ text: `Could not rescan the apps: ${requestError(err)}`, warn: true })
    } finally {
      setRescanning(false)
      reload(true)
    }
  }

  if (error) return <div className="text-sm text-destructive">Failed to load apps: {error}</div>

  return (
    <div className="flex flex-col gap-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div role="tablist" aria-label="Apps" className="flex gap-1 rounded-lg bg-muted p-1">
          {TABS.map(({ id, label, title }) => (
            <button key={id} type="button" role="tab" aria-selected={tab === id} title={title} onClick={() => setTab(id)}
                    className={cn('flex cursor-pointer items-center gap-1.5 rounded-md px-2.5 py-1 text-sm transition-colors',
                      tab === id ? 'bg-background font-medium text-foreground shadow-xs' : 'text-muted-foreground hover:text-foreground')}>
              {label}
              {data && <span className="text-xs text-muted-foreground tabular-nums">{counts[id]}</span>}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative">
            <SearchIcon className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Escape' && setQuery('')}
              placeholder={tab === 'marketplace' ? 'Search the marketplace…' : 'Filter apps…'}
              aria-label="Filter apps"
              className="h-8 w-48 pr-7 pl-8 [&::-webkit-search-cancel-button]:hidden"
            />
            {query && (
              <button type="button" aria-label="Clear the filter" onClick={() => setQuery('')}
                      className="absolute top-1/2 right-2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
                <XIcon className="size-3.5" />
              </button>
            )}
          </div>
          <Button size="sm" variant="ghost" onClick={() => reload()} disabled={loading}>
            <RefreshCwIcon className={loading ? 'animate-spin' : ''} /> Refresh
          </Button>
          <span title={daemonRunning ? 'Pick up new, removed and changed apps' : 'The geenii daemon is not running'}>
            <Button size="sm" variant="outline" onClick={rescan} disabled={!daemonRunning || rescanning}>
              <FolderSyncIcon className={rescanning ? 'animate-pulse' : ''} /> Rescan
            </Button>
          </span>
          <AddAppDialog
            daemonRunning={daemonRunning}
            onAdded={(app) => {
              setTab('available')
              onDone(`Added "${app.title}" from ${app.path}. Install it to use it.`)
            }}
          />
        </div>
      </div>
      <Notice notice={notice} onDismiss={() => setNotice(null)} />
      {data && !daemonRunning && <DaemonNotRunning what="app settings can't be changed" />}
      {data && tab !== 'marketplace' && shown.length === 0 && (
        <div className="text-sm text-muted-foreground">
          {query.trim() ? <>No apps match “{query.trim()}”.</> : tab === 'installed'
            ? byTab.available.length > 0 ? 'No apps installed. Install one from the Available tab.' : 'No apps installed.'
            : 'No other apps found. Use Add App to add one, then Rescan.'}
        </div>
      )}

      {FEATURE_APPS_MARKETPLACE && tab === 'marketplace' && (
        <div role="tabpanel"><MarketplaceView apps={apps} query={query} onDone={(text, warn) => setNotice({ text, warn })} /></div>
      )}

      {tab !== 'marketplace' && (
        <div role="tabpanel" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {shown.map((app) => <AppCard key={app.name} app={app} daemonRunning={daemonRunning} onDone={onDone} />)}
        </div>
      )}
    </div>
  )
}

export default AppsSettings
