import React, { PropsWithChildren, useCallback, useContext } from "react";
import { XAI_API_URL } from '@/constants.ts'

type McpServersContextType = {
    servers: McpServer[];
}

const McpServersContext = React.createContext<McpServersContextType | null>(null)


export const McpServersProvider = ({ children }: PropsWithChildren) => {
    const [servers, setServers] = React.useState<McpServer[]>([]);

    const fetchServers = useCallback(async () => {
        try {
            const response = await fetch(XAI_API_URL + `api/mcp/servers`)
            if (response.ok) {
                const mcpServerData = await response.json()
                setServers(mcpServerData);
            } else {
                console.error("Failed to fetch MCP servers:", response.statusText)
            }
        } catch (error) {
            console.error("Error fetching MCP servers:", error)
            setServers([]);
        }
    }, [setServers])

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
