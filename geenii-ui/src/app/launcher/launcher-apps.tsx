import React from 'react'
import { LoaderIcon, PlayIcon, SettingsIcon, SquareIcon } from 'lucide-react'
import { cn } from 'cn'
import { Skeleton } from '@/components/ui/skeleton.tsx'
import { useNavigate } from '@/app-router.tsx'
import { AppAction, GeeAppInfo, isActive, requestError, useAppAction, useAppIconUrl } from '@/app/apps/apps-api.ts'
import { AppStatusDot, DaemonNotRunning, Notice } from '@/app/apps/apps-components.tsx'

export const matchesAppQuery = (app: GeeAppInfo, query: string) => {
  const q = query.trim().toLowerCase()
  if (!q) return true
  return [app.name, app.title, app.description, app.type].some((v) => v?.toLowerCase().includes(q))
}

export const appPageUrl = (app: GeeAppInfo) => `/apps/${encodeURIComponent(app.name)}`

const AppIcon = ({ app }: { app: GeeAppInfo }) => {
  const iconUrl = useAppIconUrl(app.name)
  return (
    <div
      className={cn(
        'relative flex size-24 items-center justify-center rounded-[26px] border bg-card p-4 select-none',
        'shadow-[0_1px_2px_rgba(0,0,0,0.15),0_4px_12px_rgba(0,0,0,0.08)]',
        'transition-transform duration-200 ease-out group-hover:scale-[1.06] group-active:scale-95',
        !app.enabled && 'opacity-40 grayscale',
      )}
    >
      <img src={iconUrl} alt="" className="size-full object-contain" draggable={false} />
      <AppStatusDot app={app} className="absolute -top-0.5 -right-0.5 size-3.5 ring-2 ring-background" />
    </div>
  )
}

/**
 * An app tile: clicking opens the app page, starting the app first if it is stopped.
 * The corner button starts or stops it without leaving the launcher.
 */
const AppTile = ({ app, daemonRunning, busy, onAction }: {
  app: GeeAppInfo
  daemonRunning: boolean
  busy: AppAction | null
  onAction: (app: GeeAppInfo, action: AppAction, open?: boolean) => void
}) => {
  const navigate = useNavigate()
  const active = isActive(app)
  const canStart = daemonRunning && app.enabled && !active

  const open = (e: React.MouseEvent) => {
    e.preventDefault()
    if (busy) return
    if (canStart) onAction(app, 'start', true)
    else navigate(appPageUrl(app))
  }

  const toggle = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    onAction(app, active ? 'stop' : 'start')
  }

  const hint = !app.enabled ? 'disabled'
    : !daemonRunning ? 'daemon not running'
      : active ? 'open' : 'start and open'

  return (
    <div className="group relative flex w-36 flex-col items-center">
      <a
        href={`#${appPageUrl(app)}`}
        onClick={open}
        className="flex max-w-full flex-col items-center gap-2 rounded-2xl p-2 outline-none focus-visible:ring-2 focus-visible:ring-ring"
        title={`${app.title}${app.description ? ` — ${app.description}` : ''} (${hint})`}
      >
        <AppIcon app={app} />
        <span className={cn('line-clamp-2 max-w-full text-center text-sm leading-tight break-words', !app.enabled && 'text-muted-foreground')}>
          {app.title}
        </span>
      </a>
      {daemonRunning && app.enabled && (
        <button
          type="button"
          onClick={toggle}
          disabled={!!busy}
          aria-label={`${active ? 'Stop' : 'Start'} ${app.title}`}
          title={active ? 'Stop' : 'Start in the background'}
          className={cn(
            'absolute top-0.5 left-1.5 rounded-full border bg-background p-1 text-muted-foreground shadow-sm',
            'opacity-0 transition-opacity group-hover:opacity-100 focus-visible:opacity-100 hover:text-foreground',
            busy && 'opacity-100',
          )}
        >
          {busy ? <LoaderIcon size={12} className="animate-spin" />
            : active ? <SquareIcon size={12} /> : <PlayIcon size={12} />}
        </button>
      )}
    </div>
  )
}

const TileSkeleton = () => (
  <div className="flex w-36 flex-col items-center gap-2 p-2">
    <Skeleton className="size-24 rounded-[26px]" />
    <Skeleton className="h-3 w-14" />
  </div>
)

/** The launcher's apps tab: icon tiles of the apps, filtered by the launcher search */
const LauncherApps = ({ apps, daemonRunning, loading, error, query, reload }: {
  apps: GeeAppInfo[] | null
  daemonRunning: boolean
  loading: boolean
  error: string | null
  query: string
  reload: (quiet?: boolean) => void
}) => {
  const navigate = useNavigate()
  const runAction = useAppAction()
  const [busy, setBusy] = React.useState<Record<string, AppAction>>({})
  const [notice, setNotice] = React.useState<{ text: string, warn?: boolean } | null>(null)

  const onAction = async (app: GeeAppInfo, action: AppAction, open = false) => {
    setBusy((b) => ({ ...b, [app.name]: action }))
    try {
      await runAction(app.name, action)
      if (open) {
        navigate(appPageUrl(app))
        return
      }
      setNotice({ text: `${action === 'stop' ? 'Stopped' : 'Started'} "${app.title}".` })
    } catch (err) {
      setNotice({ text: `Could not ${action} "${app.title}": ${requestError(err)}`, warn: true })
    } finally {
      setBusy(({ [app.name]: _, ...rest }) => rest)
      reload(true)
      // the settled state, after the spawn or a quick crash
      setTimeout(() => reload(true), 1500)
    }
  }

  const visible = (apps ?? []).filter((a) => matchesAppQuery(a, query))

  if (error) {
    return <div className="rounded-lg border border-destructive/50 p-4 text-sm text-destructive">Failed to load apps: {error}</div>
  }

  return (
    <div className="flex w-full flex-col items-center gap-6">
      {notice && <div className="w-full max-w-xl"><Notice notice={notice} onDismiss={() => setNotice(null)} /></div>}
      {apps && !daemonRunning && <div className="w-full max-w-xl"><DaemonNotRunning what="apps can't be started" /></div>}

      {!apps && loading && (
        <section className="flex w-full flex-wrap justify-center gap-x-4 gap-y-6">
          {[0, 1, 2, 3].map((i) => <TileSkeleton key={i} />)}
        </section>
      )}

      {visible.length > 0 && (
        <section role="tabpanel" className="flex w-full flex-wrap justify-center gap-x-4 gap-y-6">
          {visible.map((app) => (
            <AppTile key={app.name} app={app} daemonRunning={daemonRunning} busy={busy[app.name] ?? null} onAction={onAction} />
          ))}
        </section>
      )}

      {apps && query && visible.length === 0 && (
        <p className="text-sm text-muted-foreground">No apps match “{query}”</p>
      )}

      {apps && (
        <a
          href="#/console/configure/apps"
          className="flex items-center gap-1.5 rounded-sm text-sm text-muted-foreground outline-none underline-offset-4 hover:text-foreground hover:underline focus-visible:ring-2 focus-visible:ring-ring"
        >
          <SettingsIcon size={14} /> Manage your apps
        </a>
      )}
    </div>
  )
}

export default LauncherApps
