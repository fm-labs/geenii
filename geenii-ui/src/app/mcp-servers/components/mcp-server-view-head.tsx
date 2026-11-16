import React from 'react'
import { PencilIcon, RotateCwIcon, ServerIcon, Trash2Icon, XIcon } from 'lucide-react'
import { useMcpServer } from '@/app/mcp-servers/components/mcp-server-provider.tsx'
import McpServerStatusBadge from '@/app/mcp-servers/components/mcp-server-status-badge.tsx'
import { Badge } from '@/components/ui/badge.tsx'
import { Button } from '@/components/ui/button.tsx'
import { CardDescription, CardHeader, CardTitle } from '@/components/ui/card.tsx'

export const mcpServerTarget = (server: McpServer) =>
  server.command ? [server.command, ...(server.args || [])].join(' ') : server.url || ''

type McpServerViewHeadProps = {
  /** Tool discovery status, shown as a badge, with the error when loading failed */
  status?: McpServerLoadStatus
  onReload?: () => void
  onClose?: () => void
  onEdit?: () => void
  onDelete?: () => void
}

const McpServerViewHead = ({ status, onReload, onClose, onEdit, onDelete }: McpServerViewHeadProps) => {
  const { server } = useMcpServer()
  const busy = status?.state === 'queued' || status?.state === 'loading'

  return (
    <CardHeader>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <CardTitle className="flex items-center gap-2">
            <ServerIcon size={16} className="shrink-0" /> <span className="truncate">{server.name}</span>
            {server.type && <Badge variant="secondary">{server.type}</Badge>}
            <McpServerStatusBadge status={status} />
          </CardTitle>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          {onReload && (
            <Button size="sm" variant="ghost" onClick={onReload} disabled={busy}
                    title="Start the server again and reload its tools">
              <RotateCwIcon className={busy ? 'animate-spin' : ''} /> Reload
            </Button>
          )}
          {onEdit && (
            <Button size="sm" variant="ghost" onClick={onEdit} title="Edit configuration">
              <PencilIcon /> Edit
            </Button>
          )}
          {onDelete && (
            <Button size="icon" variant="ghost" onClick={onDelete} title="Delete server">
              <Trash2Icon />
            </Button>
          )}
          {onClose && (
            <Button size="icon" variant="ghost" onClick={onClose} title="Close">
              <XIcon />
            </Button>
          )}
        </div>
      </div>
      <CardDescription className="font-mono text-xs break-all">
        {mcpServerTarget(server)}
      </CardDescription>
      {status?.state === 'failed' && status.error && (
        <p className="text-xs break-words text-destructive">Loading tools failed: {status.error}</p>
      )}
    </CardHeader>
  )
}

export default McpServerViewHead
