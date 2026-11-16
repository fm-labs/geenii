import React from 'react'
import { CircleAlertIcon, CircleCheckIcon, CircleDashedIcon, Loader2Icon } from 'lucide-react'
import { Badge } from '@/components/ui/badge.tsx'

const describe = (status: McpServerLoadStatus): string => {
  switch (status.state) {
    case 'pending':
      return 'Tools not loaded yet. They are loaded when an agent needs this server, or on reload.'
    case 'queued':
      return 'Waiting for other servers to finish loading.'
    case 'loading':
      return 'Starting the server and listing its tools. This can take a while, e.g. while a docker image is pulled.'
    case 'ready':
      return `${status.tool_count} tool${status.tool_count === 1 ? '' : 's'} available to agents.`
    case 'failed':
      return `Loading failed${status.attempts > 1 ? ` (${status.attempts} attempts)` : ''}: ${status.error || 'unknown error'}`
  }
}

/** Tool discovery status of an MCP server. Renders nothing without a status. */
const McpServerStatusBadge = ({ status }: { status?: McpServerLoadStatus }) => {
  if (!status) return null
  const title = describe(status)

  switch (status.state) {
    case 'pending':
      return <Badge variant="outline" className="text-muted-foreground" title={title}><CircleDashedIcon /> not loaded</Badge>
    case 'queued':
      return <Badge variant="outline" className="text-muted-foreground" title={title}><Loader2Icon className="animate-spin" /> queued</Badge>
    case 'loading':
      return <Badge variant="secondary" title={title}><Loader2Icon className="animate-spin" /> loading</Badge>
    case 'ready':
      return (
        <Badge variant="outline" title={title}>
          <CircleCheckIcon className="text-green-600 dark:text-green-500" /> {status.tool_count} tool{status.tool_count === 1 ? '' : 's'}
        </Badge>
      )
    case 'failed':
      return <Badge variant="destructive" title={title}><CircleAlertIcon /> failed</Badge>
  }
}

export default McpServerStatusBadge
