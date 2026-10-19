import React from 'react'
import { ChevronRightIcon, RefreshCwIcon, WrenchIcon } from 'lucide-react'
import McpServerToolForm from '@/app/mcp-servers/components/mcp-server-tool-form.tsx'
import { useMcpServer } from '@/app/mcp-servers/components/mcp-server-provider.tsx'
import { ParametersTable } from '@/app/tools/tools.view.tsx'
import { Button } from '@/components/ui/button.tsx'
import { Skeleton } from '@/components/ui/skeleton.tsx'
import { cn } from 'cn'

/** Tools provided by the server; fetched when mounted */
const McpServerActions = () => {
  const { tools, loading, loaded, error, fetchTools } = useMcpServer()
  const [selectedToolName, setSelectedToolName] = React.useState<string | null>(null)

  React.useEffect(() => {
    if (!loaded) fetchTools()
  }, [loaded, fetchTools])

  return (
    <section className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-2">
        <h4 className="text-sm font-semibold">
          Tools {loaded && !error && <span className="font-normal text-muted-foreground">({tools.length})</span>}
        </h4>
        <Button size="sm" variant="ghost" onClick={fetchTools} disabled={loading}>
          <RefreshCwIcon className={loading ? 'animate-spin' : ''} /> Refresh
        </Button>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/50 p-4 text-sm text-destructive">
          Failed to connect to server: {error}
        </div>
      )}

      {loading && tools.length === 0 && (
        <div className="flex flex-col gap-2">
          {[0, 1, 2].map((i) => <Skeleton key={i} className="h-10 w-full rounded-md" />)}
        </div>
      )}

      {loaded && !loading && !error && tools.length === 0 && (
        <p className="text-sm text-muted-foreground">This server provides no tools.</p>
      )}

      <div className="flex flex-col divide-y rounded-md border empty:hidden">
        {tools.map((tool) => {
          const isOpen = tool.name === selectedToolName
          return (
            <div key={tool.name}>
              <button type="button"
                      className="flex w-full cursor-pointer items-start gap-2 px-3 py-2 text-left hover:bg-muted/50"
                      onClick={() => setSelectedToolName(isOpen ? null : tool.name)}>
                <ChevronRightIcon size={16} className={cn('mt-0.5 shrink-0 transition-transform', isOpen && 'rotate-90')} />
                <div className="min-w-0">
                  <div className="flex items-center gap-2 font-mono text-sm">
                    <WrenchIcon size={14} className="shrink-0" /> {tool.name}
                  </div>
                  {tool.description && (
                    <p className={cn('text-sm text-muted-foreground whitespace-pre-line', !isOpen && 'line-clamp-1')}>
                      {tool.description.trim()}
                    </p>
                  )}
                </div>
              </button>
              {isOpen && (
                <div className="flex flex-col gap-4 px-3 pb-4 pt-2">
                  <ParametersTable schema={tool.input_schema} />
                  <McpServerToolForm key={tool.name} tool={tool} />
                </div>
              )}
            </div>
          )
        })}
      </div>
    </section>
  )
}

export default McpServerActions
