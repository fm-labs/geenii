import React, { PropsWithChildren, useContext } from "react";
import { ServerContext } from '@/context/ServerContext.tsx'

type McpServerContextType = {
    serverName: string;
    server: McpServer;
    tools: McpServerTool[],
    prompts?: any
    resources?: any
    fetchTools: () => Promise<McpServerTool[]>;
    callTool: (toolName: string, toolArgs?: string[]) => Promise<any>;
}

const McpServerContext = React.createContext<McpServerContextType | null>(null)


export const McpServerProvider = ({ children, server, serverName }: PropsWithChildren<{serverName: string, server: McpServer}>) => {
    const [tools, setTools] = React.useState<any[]>([])
    const { serverUrl } = React.useContext(ServerContext)

    const fetchTools = React.useCallback(async () => {
        // const response = await api.get(`/api/mcp-servers/${serverName}/tools`)
        // setTools(response)
        // return response
        try {
            const response = await fetch(`${serverUrl}api/mcp/servers/${serverName}`)
            if (response.ok) {
                const data = await response.json()
                console.log(data)
                setTools(data?.tools)
                return data
            } else {
                console.error("Failed to fetch tools:", response.statusText)
            }
        } catch (error) {
            console.error("Error fetching tools:", error)
            setTools([])
        }
    }, [serverName, setTools])

    const callTool = React.useCallback(async (toolName: string, toolInput?: any) => {
        // // @todo lookup tool
        // // @todo validate inputs
        // return await api.post(`/api/mcp-servers/${serverName}/tools/${toolName}/call`, toolInput)
        try {
            const response =await fetch(`${serverUrl}api/mcp/servers/${serverName}/tool/call`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({ server_name: serverName, tool_name: toolName, arguments: toolInput })
            })
            if (response.ok) {
                const data = await response.json()
                return data
            } else {
                console.error("Failed to call tool:", response.statusText)
            }
        } catch (error) {
            console.error("Error calling tool:", error)
        }
    }, [serverName])

    React.useEffect(() => {
        setTools([])
    }, [server])

    return (<McpServerContext.Provider value={{serverName, server, tools, fetchTools, callTool}}>
        {children}
    </McpServerContext.Provider>)
}

export const useMcpServer = () => {
    const context = useContext(McpServerContext);
    if (!context) {
        throw new Error("useMcpServers must be used within Mcp servers.");
    }
    return context;
}
