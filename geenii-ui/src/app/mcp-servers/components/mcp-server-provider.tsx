import React, { PropsWithChildren, useContext } from "react";
import { useApi } from '@/context/api-context.tsx'

type McpServerContextType = {
    serverName: string;
    server: McpServer;
    tools: McpServerTool[],
    resources: any[]
    loading: boolean;
    error: string | null;
    /** true once tools have been fetched (successfully or not) */
    loaded: boolean;
    fetchTools: () => Promise<void>;
    /** Calls a tool on the server. Throws an ApiError on failure. */
    callTool: (toolName: string, toolArgs?: any) => Promise<any>;
}

const McpServerContext = React.createContext<McpServerContextType | null>(null)


export const McpServerProvider = ({ children, server, serverName }: PropsWithChildren<{serverName: string, server: McpServer}>) => {
    const { fetchJson } = useApi()
    const [tools, setTools] = React.useState<McpServerTool[]>([])
    const [resources, setResources] = React.useState<any[]>([])
    const [loading, setLoading] = React.useState<boolean>(false)
    const [loaded, setLoaded] = React.useState<boolean>(false)
    const [error, setError] = React.useState<string | null>(null)

    const fetchTools = React.useCallback(async () => {
        setLoading(true)
        setError(null)
        try {
            const data = await fetchJson(`/api/v1/mcp/servers/${encodeURIComponent(serverName)}`)
            setTools([...(data?.tools || [])].sort((a, b) => a.name.localeCompare(b.name)))
            setResources(data?.resources || [])
        } catch (error) {
            console.error("Error fetching tools:", error)
            setError(error?.message || 'Unknown error')
            setTools([])
            setResources([])
        } finally {
            setLoading(false)
            setLoaded(true)
        }
    }, [fetchJson, serverName])

    const callTool = React.useCallback(async (toolName: string, toolInput?: any) => {
        return await fetchJson(`/api/v1/mcp/servers/${encodeURIComponent(serverName)}/tool/call`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ tool_name: toolName, arguments: toolInput || {} })
        })
    }, [fetchJson, serverName])

    const value = React.useMemo(
      () => ({ serverName, server, tools, resources, loading, loaded, error, fetchTools, callTool }),
      [serverName, server, tools, resources, loading, loaded, error, fetchTools, callTool])

    return (<McpServerContext.Provider value={value}>
        {children}
    </McpServerContext.Provider>)
}

export const useMcpServer = () => {
    const context = useContext(McpServerContext);
    if (!context) {
        throw new Error("useMcpServer must be used within McpServerProvider.");
    }
    return context;
}
