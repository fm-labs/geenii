import React from "react";

type DockerMcpCatalogItemContextType = {}

const DockerMcpCatalogItemContext = React.createContext<DockerMcpCatalogItemContextType | null>(null)

export const DockerMcpCatalogItemProvider = ({ children }: React.PropsWithChildren) => {
    return (<DockerMcpCatalogItemContext.Provider value={{}}>{children}</DockerMcpCatalogItemContext.Provider>)
}

export const useDockerMcpCatalogItem = () => {
    const context = React.useContext(DockerMcpCatalogItemContext);
    if (!context) {
        throw new Error('useDockerMcpCatalogItem must be used within DockerMcpCatalogItemProvider')
    }
    return context
}
