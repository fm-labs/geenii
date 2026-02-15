import { createContext, PropsWithChildren, useContext, useState, useEffect } from "react";

type DockerMcpCatalog = {
    version: number;
    name: string;
    displayName: string;
    registry: { [key: string]: any };
}

type DockerMcpCatalogContextType = DockerMcpCatalog & {
    getServerDef: (name: string) => any;
}

const DockerMcpCatalogContext = createContext<DockerMcpCatalogContextType | null>(null)



export const DockerMcpCatalogProvider = ({children}: PropsWithChildren) => {
    //const mcpCatalog = mcpCatalogData as DockerMcpCatalog;
    const [mcpCatalog, setMcpCatalog] = useState<DockerMcpCatalog>()

    const getServerDef = (name: string): any => {
        return mcpCatalog.registry[name] || null
    }

    const contextValue = {
        ...mcpCatalog,
        getServerDef
    }

    const fetchCatalog = async () => {
        try {
            const response = await fetch('/assets/docker-mcp-catalog.json');
            if (!response.ok) {
                throw new Error(`Failed to fetch MCP catalog: ${response.statusText}`);
            }
            const data = await response.json();
            setMcpCatalog(data);
        } catch (error) {
            console.error('Error fetching MCP catalog:', error);
        }
    }

    useEffect(() => {
        fetchCatalog();
    }, [])

    return <DockerMcpCatalogContext.Provider value={contextValue}>
        {children}
    </DockerMcpCatalogContext.Provider>
}

export const useDockerMcpCatalog = () => {
    const context = useContext(DockerMcpCatalogContext);
    if (!context) {
        throw new Error('useDockerMcpCatalog must be used within DockerMcpCatalogProvider')
    }
    return context
}
