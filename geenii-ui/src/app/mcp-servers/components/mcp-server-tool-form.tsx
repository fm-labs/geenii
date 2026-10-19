import React from "react";
import Form from "@rjsf/shadcn";
import validator from "@rjsf/validator-ajv8";
import { LoaderIcon, PlayIcon } from 'lucide-react'
import { useMcpServer } from "@/app/mcp-servers/components/mcp-server-provider.tsx";
import JsonView from "@/components/json-view.tsx";
import { Badge } from '@/components/ui/badge.tsx'
import { Button } from '@/components/ui/button.tsx'
import { cn } from 'cn'

type ExecutionResult = {
    ok: boolean;
    output: any;
    durationMs: number;
}

/** Text parts of an MCP CallToolResult, joined */
const resultText = (result: any): string | null => {
    const texts = (result?.content || []).filter((c: any) => c?.type === 'text').map((c: any) => c.text)
    return texts.length > 0 ? texts.join('\n') : null
}

const McpServerToolForm = ({ tool }: { tool: McpServerTool }) => {
    const { callTool } = useMcpServer();
    const [formData, setFormData] = React.useState<any>({})
    const [isExecuting, setIsExecuting] = React.useState(false)
    const [result, setResult] = React.useState<ExecutionResult | null>(null)

    const handleSubmit = React.useCallback(async ({ formData }: { formData?: any }) => {
        setIsExecuting(true)
        setResult(null)
        const start = performance.now()
        try {
            const output = await callTool(tool.name, formData || {});
            setResult({ ok: !output?.is_error, output, durationMs: performance.now() - start });
        } catch (error) {
            setResult({ ok: false, output: error?.message || String(error), durationMs: performance.now() - start });
        } finally {
            setIsExecuting(false)
        }
    }, [callTool, tool.name]);

    const text = result && typeof result.output !== 'string' ? resultText(result.output) : null
    const structured = result?.output?.structured_content

    return (
        <div className="flex flex-col gap-4">
            <Form schema={tool?.input_schema || { type: 'object' }}
                  validator={validator}
                  formData={formData}
                  onChange={(e) => setFormData(e.formData)}
                  onSubmit={handleSubmit}
                  disabled={isExecuting}
            >
                <div className="mt-4 flex justify-end">
                    <Button type="submit" size="sm" disabled={isExecuting}>
                        {isExecuting ? <LoaderIcon className="animate-spin" /> : <PlayIcon />}
                        {isExecuting ? 'Executing ...' : 'Execute'}
                    </Button>
                </div>
            </Form>

            {result && (
                <section className="flex flex-col gap-2">
                    <h4 className="flex items-center gap-2 text-sm font-semibold">
                        Result
                        <Badge variant={result.ok ? 'secondary' : 'destructive'}>{result.ok ? 'success' : 'error'}</Badge>
                        <span className="text-xs font-normal text-muted-foreground">{Math.round(result.durationMs)} ms</span>
                    </h4>
                    {typeof result.output === 'string' || text !== null ? (
                        <pre className={cn('max-h-96 overflow-auto rounded-md border bg-muted p-3 text-xs whitespace-pre-wrap',
                          !result.ok && 'border-destructive/50 text-destructive')}>
                            {(typeof result.output === 'string' ? result.output : text)
                              || <span className="italic text-muted-foreground">(empty output)</span>}
                        </pre>
                    ) : null}
                    {structured && <JsonView src={structured} className="max-w-full" />}
                    {typeof result.output !== 'string' && <JsonView src={result.output} collapsed={true} className="max-w-full" />}
                </section>
            )}
        </div>
    );
};

export default McpServerToolForm;
