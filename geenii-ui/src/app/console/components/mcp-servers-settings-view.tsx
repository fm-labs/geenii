import * as React from 'react'
import { PlusIcon, RefreshCwIcon, SearchIcon, ServerIcon } from 'lucide-react'
import { McpServersProvider, useMcpServers } from '@/app/mcp-servers/components/mcp-servers-provider.tsx'
import { McpServer } from '@/app/mcp-servers/components/mcp-server.tsx'
import { McpServerProvider } from '@/app/mcp-servers/components/mcp-server-provider.tsx'
import McpServerViewHead, { mcpServerTarget } from '@/app/mcp-servers/components/mcp-server-view-head.tsx'
import McpServerActions from '@/app/mcp-servers/components/mcp-server-actions.tsx'
import McpServerConfigEditor from '@/app/mcp-servers/components/mcp-server-config-editor.tsx'
import { Badge } from '@/components/ui/badge.tsx'
import { Button } from '@/components/ui/button.tsx'
import { Card, CardContent } from '@/components/ui/card.tsx'
import { Input } from '@/components/ui/input.tsx'
import { Skeleton } from '@/components/ui/skeleton.tsx'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet.tsx'
import { cn } from 'cn'

const McpServersAdminView = () => {
  const { servers, loading, error, refresh, getServerConfig, createServer, updateServer, deleteServer } = useMcpServers()
  const [filter, setFilter] = React.useState<string>('')
  const [selectedServerName, setSelectedServerName] = React.useState<string | null>(null)

  const filtered = React.useMemo(() => {
    const q = filter.trim().toLowerCase()
    return servers.filter((s) => !q || s.name.toLowerCase().includes(q) || mcpServerTarget(s).toLowerCase().includes(q))
  }, [servers, filter])

  const selectedServer = servers.find((s) => s.name === selectedServerName) || null
  // undefined: editor closed, null: new server, otherwise the server being edited
  const [editing, setEditing] = React.useState<{ name: string, config: McpServerConfig } | null | undefined>(undefined)
  const [actionError, setActionError] = React.useState<string | null>(null)

  const editServer = async (name: string) => {
    setActionError(null)
    try {
      setEditing({ name, config: await getServerConfig(name) })
    } catch (e: any) {
      setActionError(`Failed to load the configuration of ${name}: ${e?.message || e}`)
    }
  }

  const saveServer = async (name: string, config: McpServerConfig) => {
    if (editing) {
      await updateServer(name, config)
    } else {
      await createServer(name, config)
      setSelectedServerName(name)
    }
    setEditing(undefined)
  }

  const removeServer = async (name: string) => {
    if (!window.confirm(`Delete the MCP server "${name}"? This removes it from mcp.json.`)) return
    setActionError(null)
    try {
      await deleteServer(name)
      setSelectedServerName(null)
    } catch (e: any) {
      setActionError(`Failed to delete ${name}: ${e?.message || e}`)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-2">
        <div className="relative w-full max-w-xs">
          <SearchIcon size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input className="pl-8" placeholder="Filter servers ..." value={filter} onChange={(e) => setFilter(e.target.value)} />
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground whitespace-nowrap">
            {!loading && !error && `${servers.length} server${servers.length === 1 ? '' : 's'}`}
          </span>
          <Button size="sm" variant="ghost" onClick={() => refresh(true)} disabled={loading}>
            <RefreshCwIcon className={loading ? 'animate-spin' : ''} /> Refresh
          </Button>
          <Button size="sm" onClick={() => setEditing(null)}>
            <PlusIcon /> Add server
          </Button>
        </div>
      </div>

      {actionError && (
        <div className="rounded-lg border border-destructive/50 p-4 text-sm text-destructive">{actionError}</div>
      )}

      {error && (
        <div className="rounded-lg border border-destructive/50 p-4 text-sm text-destructive">
          Failed to load MCP servers: {error}
        </div>
      )}

      <div className={cn('grid gap-6', selectedServer && 'lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]')}>
        <div className="flex flex-col gap-2">
          {loading && servers.length === 0 && [0, 1, 2].map((i) => <Skeleton key={i} className="h-14 w-full rounded-md" />)}
          {!loading && !error && filtered.length === 0 && (
            <p className="text-sm text-muted-foreground">{filter ? 'No servers match the filter.' : 'No MCP servers configured.'}</p>
          )}
          {filtered.map((server) => (
            <button key={server.name} type="button"
                    className={cn('flex w-full cursor-pointer items-start gap-3 rounded-md border px-3 py-2 text-left hover:bg-muted/50',
                      server.name === selectedServerName && 'border-primary bg-muted')}
                    onClick={() => setSelectedServerName(server.name === selectedServerName ? null : server.name)}>
              <ServerIcon size={16} className="mt-0.5 shrink-0" />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <span className="truncate">{server.name}</span>
                  {server.type && <Badge variant="outline">{server.type}</Badge>}
                </div>
                <p className="truncate font-mono text-xs text-muted-foreground" title={mcpServerTarget(server)}>
                  {mcpServerTarget(server)}
                </p>
              </div>
            </button>
          ))}
        </div>

        {selectedServer && (
          <div className="lg:sticky lg:top-20 lg:self-start">
            {/* keyed by name, so tools are fetched once per selected server */}
            <McpServerProvider key={selectedServer.name} serverName={selectedServer.name} server={selectedServer}>
              <Card className="gap-4">
                <McpServerViewHead onClose={() => setSelectedServerName(null)} onEdit={() => editServer(selectedServer.name)}
                                   onDelete={() => removeServer(selectedServer.name)} />
                <CardContent className="flex flex-col gap-6">
                  <McpServer />
                  <McpServerActions />
                </CardContent>
              </Card>
            </McpServerProvider>
          </div>
        )}
      </div>

      <Sheet open={editing !== undefined} onOpenChange={(open) => !open && setEditing(undefined)}>
        <SheetContent className="w-full gap-0 sm:max-w-xl">
          <SheetHeader>
            <SheetTitle>{editing ? `Edit ${editing.name}` : 'Add MCP server'}</SheetTitle>
            <SheetDescription>
              {editing
                ? 'Change how geenii starts or connects to this server. Masked values stay as they are unless you replace them.'
                : 'Run a local server as a process, or connect to a remote one over HTTP.'}
            </SheetDescription>
          </SheetHeader>
          {editing !== undefined && (
            <McpServerConfigEditor key={editing?.name ?? '__new__'}
                                   serverName={editing?.name}
                                   initialConfig={editing?.config}
                                   existingNames={servers.map((s) => s.name)}
                                   onSubmit={saveServer}
                                   onCancel={() => setEditing(undefined)} />
          )}
        </SheetContent>
      </Sheet>
    </div>
  )
}

export const McpServersSettingsView = () => {
  return (
    <McpServersProvider>
      <McpServersAdminView />
    </McpServersProvider>
  )
}
