import React, { PropsWithChildren, useCallback, useContext } from "react";
import { useApi } from '@/context/api-context.tsx'
import { ApiError, readProblem } from '@/api/api-error.ts'

type McpServersContextType = {
    servers: McpServer[];
    loading: boolean;
    error: string | null;
    refresh: (reload?: boolean) => Promise<void>;
    /** Full mcp.json entry of a server, with env and header values masked */
    getServerConfig: (name: string) => Promise<McpServerConfig>;
    /** These write the root mcp.json, refresh the list and throw an ApiError on failure */
    createServer: (name: string, config: McpServerConfig) => Promise<void>;
    updateServer: (name: string, config: McpServerConfig) => Promise<void>;
    deleteServer: (name: string) => Promise<void>;
}

const McpServersContext = React.createContext<McpServersContextType | null>(null)


export const McpServersProvider = ({ children }: PropsWithChildren) => {
    const { fetch, fetchJson } = useApi()
    const [servers, setServers] = React.useState<McpServer[]>([]);
    const [loading, setLoading] = React.useState<boolean>(true);
    const [error, setError] = React.useState<string | null>(null);

    const refresh = useCallback(async (reload: boolean = false) => {
        setLoading(true)
        setError(null)
        try {
            const data: McpServer[] = await fetchJson(`/api/v1/mcp/servers${reload ? '?reload=true' : ''}`)
            setServers([...data].sort((a, b) => a.name.localeCompare(b.name)));
        } catch (error) {
            console.error("Error fetching MCP servers:", error)
            setError(error?.message || 'Unknown error')
            setServers([]);
        } finally {
            setLoading(false)
        }
    }, [fetchJson])

    React.useEffect(() => {
        refresh()
    }, [refresh])

    const serverUrl = (name: string) => `/api/v1/mcp/servers/${encodeURIComponent(name)}`

    const getServerConfig = useCallback(async (name: string) => {
        return await fetchJson(`${serverUrl(name)}/config`)
    }, [fetchJson])

    const createServer = useCallback(async (name: string, config: McpServerConfig) => {
        await fetchJson('/api/v1/mcp/servers', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, config }),
        })
        await refresh()
    }, [fetchJson, refresh])

    const updateServer = useCallback(async (name: string, config: McpServerConfig) => {
        await fetchJson(serverUrl(name), {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config),
        })
        await refresh()
    }, [fetchJson, refresh])

    const deleteServer = useCallback(async (name: string) => {
        // 204 has no body, so fetchJson can't be used
        const response = await fetch(serverUrl(name), { method: 'DELETE' })
        if (!response.ok) {
            throw new ApiError(response.status, await readProblem(response))
        }
        await refresh()
    }, [fetch, refresh])

    const value = React.useMemo(
        () => ({ servers, loading, error, refresh, getServerConfig, createServer, updateServer, deleteServer }),
        [servers, loading, error, refresh, getServerConfig, createServer, updateServer, deleteServer])

    return (<McpServersContext.Provider value={value}>{children}</McpServersContext.Provider>)
}

export const useMcpServers = () => {
    const context = useContext(McpServersContext);
    if (!context) {
        throw new Error("useMcpServers must be used within McpServersProvider.");
    }
    return context;
}
