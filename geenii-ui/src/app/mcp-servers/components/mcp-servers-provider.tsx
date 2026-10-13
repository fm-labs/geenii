import React, { PropsWithChildren, useCallback, useContext } from "react";
import { useApi } from '@/context/api-context.tsx'

type McpServersContextType = {
    servers: McpServer[];
}

const McpServersContext = React.createContext<McpServersContextType | null>(null)


export const McpServersProvider = ({ children }: PropsWithChildren) => {
    const { fetchJson } = useApi()
    const [servers, setServers] = React.useState<McpServer[]>([]);

    const fetchServers = useCallback(async () => {
        try {
            const mcpServerData = await fetchJson(`/api/v1/mcp/servers`)
            setServers(mcpServerData);
        } catch (error) {
            console.error("Error fetching MCP servers:", error)
            setServers([]);
        }
    }, [fetchJson, setServers])

    React.useEffect(() => {
        fetchServers()
    }, [fetchServers])

    return (<McpServersContext.Provider value={{servers}}>{children}</McpServersContext.Provider>)
}

export const useMcpServers = () => {
    const context = useContext(McpServersContext);
    if (!context) {
        throw new Error("useMcpServerss must be used within Mcp servers.");
    }
    return context;
}
