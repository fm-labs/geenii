import React from 'react'
import { PencilIcon, ServerIcon, Trash2Icon, XIcon } from 'lucide-react'
import { useMcpServer } from '@/app/mcp-servers/components/mcp-server-provider.tsx'
import { Badge } from '@/components/ui/badge.tsx'
import { Button } from '@/components/ui/button.tsx'
import { CardDescription, CardHeader, CardTitle } from '@/components/ui/card.tsx'

export const mcpServerTarget = (server: McpServer) =>
  server.command ? [server.command, ...(server.args || [])].join(' ') : server.url || ''

const McpServerViewHead = ({ onClose, onEdit, onDelete }: { onClose?: () => void, onEdit?: () => void, onDelete?: () => void }) => {
  const { server } = useMcpServer()

  return (
    <CardHeader>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <CardTitle className="flex items-center gap-2">
            <ServerIcon size={16} className="shrink-0" /> <span className="truncate">{server.name}</span>
            {server.type && <Badge variant="secondary">{server.type}</Badge>}
          </CardTitle>
        </div>
        <div className="flex shrink-0 items-center gap-1">
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
    </CardHeader>
  )
}

export default McpServerViewHead
