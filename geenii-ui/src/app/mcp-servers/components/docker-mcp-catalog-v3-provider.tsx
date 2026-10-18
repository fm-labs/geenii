import { createContext, PropsWithChildren, useContext, useState, useEffect } from "react";

type DockerMcpCatalogV3 = {
    version: number;
    name: string;
    displayName: string;
    registry: { [key: string]: any };
}

type DockerMcpCatalogContextType = {
    catalog: DockerMcpCatalogV3;
    getServerDef: (name: string) => any;
}

const DockerMcpCatalogContext = createContext<DockerMcpCatalogContextType | null>(null)

/**
 * DEPRECATED: This component is deprecated and will be removed in future versions. Please use the new MCP server configuration builder instead.
 * @constructor
 * @deprecated
 */
export const DockerMcpCatalogV3Provider = ({children}: PropsWithChildren) => {
    //const mcpCatalog = mcpCatalogData as DockerMcpCatalog;
    const [mcpCatalog, setMcpCatalog] = useState<DockerMcpCatalogV3>()

    const getServerDef = (name: string): any => {
        if (!mcpCatalog) {
            console.warn('MCP Catalog not loaded yet')
            return null
        }
        return mcpCatalog.registry[name] || null
    }

    const contextValue = {
        catalog: mcpCatalog,
        getServerDef
    }

    const fetchCatalog = async () => {
        try {
            const response = await fetch('/assets/docker-mcp-catalog-v3.json');
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

/**
 * DEPRECATED: This component is deprecated and will be removed in future versions. Please use the new MCP server configuration builder instead.
 * @deprecated
 */
export const useDockerMcpCatalogV3 = () => {
    const context = useContext(DockerMcpCatalogContext);
    if (!context) {
        throw new Error('useDockerMcpCatalogV3 must be used within DockerMcpCatalogV3Provider')
    }
    return context
}
