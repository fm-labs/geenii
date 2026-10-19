import React from "react";
import { BracesIcon, ListIcon } from 'lucide-react'
import { useMcpServer } from "@/app/mcp-servers/components/mcp-server-provider.tsx";
import JsonView from "@/components/json-view.tsx";
import { Badge } from '@/components/ui/badge.tsx'
import { Button } from '@/components/ui/button.tsx'


/** Server configuration details */
export const McpServer = () => {
    const { server } = useMcpServer();
    const [showRaw, setShowRaw] = React.useState(false);
    const envKeys = Object.keys(server?.env || {});

    return (
        <section className="flex flex-col gap-2">
            <div className="flex items-center justify-between gap-2">
                <h4 className="text-sm font-semibold">Configuration</h4>
                <Button size="sm" variant="ghost" onClick={() => setShowRaw(!showRaw)} aria-pressed={showRaw}
                        title={showRaw ? 'Show details' : 'Show raw JSON'}>
                    {showRaw ? <ListIcon /> : <BracesIcon />} {showRaw ? 'Details' : 'Raw JSON'}
                </Button>
            </div>
            {showRaw ? (
                <JsonView src={server} className="max-w-full" />
            ) : (
            <dl className="grid grid-cols-[max-content_minmax(0,1fr)] gap-x-4 gap-y-1 text-sm">
                {server.command && <>
                    <dt className="text-muted-foreground">Command</dt>
                    <dd className="font-mono break-all">{server.command}</dd>
                </>}
                {server.args && server.args.length > 0 && <>
                    <dt className="text-muted-foreground">Args</dt>
                    <dd className="font-mono break-all">{server.args.join(" ")}</dd>
                </>}
                {server.url && <>
                    <dt className="text-muted-foreground">URL</dt>
                    <dd className="font-mono break-all">{server.url}</dd>
                </>}
                <dt className="text-muted-foreground">Env</dt>
                <dd className="flex flex-wrap gap-1">
                    {envKeys.length === 0
                      ? <span className="text-muted-foreground">-</span>
                      : envKeys.map((key) => <Badge key={key} variant="outline" className="font-mono">{key}</Badge>)}
                </dd>
            </dl>
            )}
        </section>
    );
};
