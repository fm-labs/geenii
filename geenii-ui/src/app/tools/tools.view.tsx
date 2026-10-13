import React from 'react'
import Form from '@rjsf/shadcn'
import validator from '@rjsf/validator-ajv8'
import { LoaderIcon, PlayIcon, RefreshCwIcon, SearchIcon, WrenchIcon, XIcon } from 'lucide-react'
import { Badge } from '@/components/ui/badge.tsx'
import { Button } from '@/components/ui/button.tsx'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.tsx'
import { Input } from '@/components/ui/input.tsx'
import { Skeleton } from '@/components/ui/skeleton.tsx'
import JsonView from '@/components/json-view.tsx'
import { useApi } from '@/context/api-context.tsx'
import { cn } from 'cn'
import { ToolType } from '@/app/tools/tool-types.ts'

type ExecutionResult = {
  ok: boolean;
  output: any;
  durationMs: number;
}

/** Error responses carry a Problem body: {error, status, detail} */
const problemMessage = (data: any) =>
  data && typeof data === 'object' ? (data.detail || data.error || data) : data

const ParametersTable = ({ schema }: { schema?: ToolType['parameters'] }) => {
  const properties = Object.entries((schema?.properties || {}) as Record<string, any>)
  const required: string[] = (schema?.required as string[]) || []
  if (properties.length === 0) {
    return <p className="text-sm text-muted-foreground">No parameters</p>
  }
  return (
    <div className="overflow-x-auto rounded-md border">
      <table className="w-full text-sm">
        <thead className="bg-muted text-left text-xs text-muted-foreground">
          <tr>
            <th className="px-3 py-2 font-medium">Name</th>
            <th className="px-3 py-2 font-medium">Type</th>
            <th className="px-3 py-2 font-medium">Description</th>
          </tr>
        </thead>
        <tbody>
          {properties.map(([name, prop]) => (
            <tr key={name} className="border-t align-top">
              <td className="px-3 py-2 font-mono whitespace-nowrap">
                {name}{required.includes(name) && <span className="text-destructive" title="required">*</span>}
              </td>
              <td className="px-3 py-2 font-mono text-muted-foreground">{prop?.type || '-'}</td>
              <td className="px-3 py-2">{prop?.description || ''}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

const ToolDetailsPane = ({ tool, onClose }: { tool: ToolType, onClose: () => void }) => {
  const { fetch } = useApi()

  const [formData, setFormData] = React.useState<any>({})
  const [isExecuting, setIsExecuting] = React.useState(false)
  const [result, setResult] = React.useState<ExecutionResult | null>(null)

  const handleSubmit = async ({ formData }: { formData?: any }) => {
    setIsExecuting(true)
    setResult(null)
    const start = performance.now()
    try {
      const response = await fetch(`/api/v1/tools/${encodeURIComponent(tool.name)}/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData || {}),
      })
      const text = await response.text()
      let output: any = text
      try {
        output = JSON.parse(text)
      } catch {
        // plain text response
      }
      setResult({
        ok: response.ok,
        output: response.ok ? output : problemMessage(output),
        durationMs: performance.now() - start,
      })
    } catch (err) {
      setResult({ ok: false, output: err?.message || String(err), durationMs: performance.now() - start })
    } finally {
      setIsExecuting(false)
    }
  }

  return (
    <Card className="gap-4">
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <CardTitle className="flex items-center gap-2 font-mono">
              <WrenchIcon size={16} className="shrink-0" /> <span className="truncate">{tool.name}</span>
            </CardTitle>
            <Badge variant="secondary" className="mt-2">{tool.type}</Badge>
          </div>
          <Button size="icon" variant="ghost" onClick={onClose} title="Close">
            <XIcon />
          </Button>
        </div>
        <CardDescription className="whitespace-pre-line">
          {tool.description?.trim() || <span className="italic">No description</span>}
        </CardDescription>
      </CardHeader>

      <CardContent className="flex flex-col gap-6">
        <section className="flex flex-col gap-2">
          <h4 className="text-sm font-semibold">Parameters</h4>
          <ParametersTable schema={tool.parameters} />
        </section>

        <section className="flex flex-col gap-2">
          <h4 className="text-sm font-semibold">Execute</h4>
          <Form schema={tool.parameters || { type: 'object' }}
                validator={validator}
                formData={formData}
                onChange={(e) => setFormData(e.formData)}
                onSubmit={handleSubmit}
                disabled={isExecuting}
          >
            <div className="mt-4 flex justify-end">
              <Button type="submit" disabled={isExecuting}>
                {isExecuting ? <LoaderIcon className="animate-spin" /> : <PlayIcon />}
                {isExecuting ? 'Executing ...' : 'Execute'}
              </Button>
            </div>
          </Form>
        </section>

        {result && (
          <section className="flex flex-col gap-2">
            <h4 className="flex items-center gap-2 text-sm font-semibold">
              Result
              <Badge variant={result.ok ? 'secondary' : 'destructive'}>{result.ok ? 'success' : 'error'}</Badge>
              <span className="text-xs font-normal text-muted-foreground">{Math.round(result.durationMs)} ms</span>
            </h4>
            {typeof result.output === 'string' ? (
              <pre className={cn('max-h-96 overflow-auto rounded-md border bg-muted p-3 text-xs whitespace-pre-wrap',
                !result.ok && 'border-destructive/50 text-destructive')}>
                {result.output || <span className="italic text-muted-foreground">(empty output)</span>}
              </pre>
            ) : (
              <JsonView src={result.output} className="max-w-full" />
            )}
          </section>
        )}
      </CardContent>
    </Card>
  )
}

const ToolsView = () => {
  const { fetchJson } = useApi()

  const [tools, setTools] = React.useState<ToolType[]>([])
  const [loading, setLoading] = React.useState<boolean>(true)
  const [error, setError] = React.useState<string | null>(null)
  const [filter, setFilter] = React.useState<string>('')
  const [selectedName, setSelectedName] = React.useState<string | null>(null)

  const fetchTools = React.useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data: ToolType[] = await fetchJson('/api/v1/tools/')
      setTools([...data].sort((a, b) => a.name.localeCompare(b.name)))
    } catch (err) {
      console.error('Error fetching tools', err)
      setError(err?.message || 'Unknown error')
    } finally {
      setLoading(false)
    }
  }, [fetchJson])

  React.useEffect(() => {
    fetchTools()
  }, [fetchTools])

  const groups = React.useMemo(() => {
    const q = filter.trim().toLowerCase()
    const matching = tools.filter((t) =>
      !q || t.name.toLowerCase().includes(q) || t.description?.toLowerCase().includes(q))
    const byType: Record<string, ToolType[]> = {}
    matching.forEach((t) => {
      (byType[t.type || 'other'] ||= []).push(t)
    })
    return Object.entries(byType).sort(([a], [b]) => a.localeCompare(b))
  }, [tools, filter])

  const selectedTool = tools.find((t) => t.name === selectedName) || null

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-2">
        <div className="relative w-full max-w-xs">
          <SearchIcon size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input className="pl-8" placeholder="Filter tools ..." value={filter} onChange={(e) => setFilter(e.target.value)} />
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground whitespace-nowrap">
            {!loading && !error && `${tools.length} tool${tools.length === 1 ? '' : 's'}`}
          </span>
          <Button size="sm" variant="ghost" onClick={fetchTools} disabled={loading}>
            <RefreshCwIcon className={loading ? 'animate-spin' : ''} /> Refresh
          </Button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/50 p-4 text-sm text-destructive">
          Failed to load tools: {error}
        </div>
      )}

      <div className={cn('grid gap-6', selectedTool && 'lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]')}>
        <div className="flex flex-col gap-4">
          {loading && tools.length === 0 && (
            <div className="flex flex-wrap gap-2">
              {[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-6 w-24 rounded-md" />)}
            </div>
          )}
          {!loading && !error && groups.length === 0 && (
            <p className="text-sm text-muted-foreground">{filter ? 'No tools match the filter.' : 'No tools registered.'}</p>
          )}
          {groups.map(([type, groupTools]) => (
            <div key={type} className="flex flex-col gap-2">
              <h4 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
                {type} <span className="font-normal">({groupTools.length})</span>
              </h4>
              <div className="flex flex-wrap gap-2">
                {groupTools.map((tool) => (
                  <Badge key={tool.name} asChild variant={tool.name === selectedName ? 'default' : 'outline'}>
                    <button type="button"
                            className="cursor-pointer px-2.5 py-1 font-mono text-sm"
                            title={tool.description?.trim() || tool.name}
                            onClick={() => setSelectedName(tool.name === selectedName ? null : tool.name)}>
                      {tool.name}
                    </button>
                  </Badge>
                ))}
              </div>
            </div>
          ))}
        </div>

        {selectedTool && (
          <div className="lg:sticky lg:top-20 lg:self-start">
            <ToolDetailsPane key={selectedTool.name} tool={selectedTool} onClose={() => setSelectedName(null)} />
          </div>
        )}
      </div>
    </div>
  )
}

export default ToolsView
