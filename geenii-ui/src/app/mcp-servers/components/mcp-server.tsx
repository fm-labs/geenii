import { useMcpServer } from "@/app/mcp-servers/components/mcp-server-provider.tsx";
import { Button } from "@/components/ui/button.tsx";
import { Separator } from "@/components/ui/separator.tsx";
import React, { useState } from "react";
import JsonView from "@/components/json-view.tsx";
import McpServerToolForm from "@/app/mcp-servers/components/mcp-server-tool-form.tsx";
import { Badge } from '@/components/ui/badge.tsx'



export const McpServer = () => {
    const { server } = useMcpServer();

    return (<div className={""}>
        <div className={"flex flex-col justify-between"}>
            {(server.type==="stdio" || server?.command) && (
                <div>
                    <Badge variant={"secondary"}>stdio</Badge>
                    {server?.command} {server?.args.join(" ")}<br />
                </div>
            )}
            {(server.type==="http" || server?.url) && (
                <div>
                    <Badge variant={"secondary"}>http</Badge> {server?.url}<br />
                </div>
            )}
            <div>
                <h3 className={"font-bold"}>env vars</h3>
                <div className={"text-sm"}>
                    {Object.entries(server?.env || {}).map(([key, value]) => {
                        return <div key={key}>
                            <span className={"font-mono font-bold"}>{key}:</span> <span className={"font-mono"}>{value}</span>
                        </div>;
                    })}
                </div>
            </div>
        </div>
    </div>);
};
