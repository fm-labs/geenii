import React from 'react'
import { CheckIcon, DownloadIcon, SearchIcon, StoreIcon } from 'lucide-react'
import { Badge } from '@/components/ui/badge.tsx'
import { Button } from '@/components/ui/button.tsx'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card.tsx'
import { AppType, GeeAppInfo } from '@/app/apps/apps-api.ts'
import catalogJson from '@/app/apps/marketplace-catalog.json'

/** An app bundle in the marketplace catalog */
export type CatalogApp = {
  name: string
  title: string
  description: string
  author: string
  version: string
  type: AppType
  tags: string[]
  size_kb: number
  /** Zip with the app directory (manifest.json at its root) */
  bundle_url: string
  sha256: string
}

/** The catalog file: a list of app bundles */
export type AppCatalog = {
  version: number
  updated: string
  apps: CatalogApp[]
}

// Dummy data until the catalog is fetched from a server
const CATALOG = catalogJson as AppCatalog

const fmtSize = (kb: number) => (kb < 1024 ? `${kb} KB` : `${(kb / 1024).toFixed(1)} MB`)

const matches = (app: CatalogApp, query: string) => {
  const q = query.trim().toLowerCase()
  if (!q) return true
  return [app.name, app.title, app.description, app.author, app.type, ...app.tags].some((v) => v.toLowerCase().includes(q))
}

/**
 * Apps from the marketplace catalog. A dummy view: installing a bundle is not implemented yet.
 * `apps` are the local apps, to mark catalog apps that are already there.
 */
const MarketplaceView = ({ apps, onDone }: {
  apps: GeeAppInfo[]
  onDone: (message: string, warn?: boolean) => void
}) => {
  const [query, setQuery] = React.useState('')
  const local = React.useMemo(() => new Map(apps.map((a) => [a.name, a])), [apps])
  const shown = CATALOG.apps.filter((a) => matches(a, query))

  const install = (app: CatalogApp) => {
    onDone(`Installing from the marketplace is not available yet ("${app.title}" ${app.version}).`, true)
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="relative w-full max-w-xs">
          <SearchIcon size={14} className="absolute top-1/2 left-2.5 -translate-y-1/2 text-muted-foreground" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search the marketplace"
            className="h-8 w-full rounded-md border bg-transparent pr-2 pl-8 text-sm outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
          />
        </div>
        <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <StoreIcon size={12} /> {CATALOG.apps.length} apps · catalog updated {new Date(CATALOG.updated).toLocaleDateString()}
        </span>
      </div>

      {shown.length === 0 && <div className="text-sm text-muted-foreground">No marketplace apps match “{query}”.</div>}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {shown.map((app) => {
          const existing = local.get(app.name)
          return (
            <Card key={app.name} className="gap-3">
              <CardHeader>
                <CardTitle className="flex items-start justify-between gap-2 text-base">
                  <span className="truncate">{app.title}</span>
                  <Badge variant="outline" className="font-mono">{app.type}</Badge>
                </CardTitle>
                <CardDescription className="text-xs">
                  {app.author} · v{app.version} · {fmtSize(app.size_kb)}
                </CardDescription>
              </CardHeader>
              <CardContent className="flex flex-1 flex-col gap-2 text-sm">
                <p className="line-clamp-3">{app.description}</p>
                <div className="flex flex-wrap gap-1">
                  {app.tags.map((t) => <Badge key={t} variant="secondary">{t}</Badge>)}
                </div>
              </CardContent>
              <CardFooter className="justify-end">
                {existing ? (
                  <Button size="sm" variant="outline" disabled title={existing.path}>
                    <CheckIcon /> {existing.enabled ? 'Installed' : 'Available'}
                  </Button>
                ) : (
                  <Button size="sm" onClick={() => install(app)}>
                    <DownloadIcon /> Install
                  </Button>
                )}
              </CardFooter>
            </Card>
          )
        })}
      </div>
    </div>
  )
}

export const MARKETPLACE_COUNT = CATALOG.apps.length

export default MarketplaceView
