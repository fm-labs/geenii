import { createContext, PropsWithChildren, useContext } from "react";
import mcpCatalogData from "../data/catalog.json"

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
    const mcpCatalog = mcpCatalogData as DockerMcpCatalog;

    const getServerDef = (name: string): any => {
        return mcpCatalog.registry[name] || null
    }

    const contextValue = {
        ...mcpCatalog,
        getServerDef
    }

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
