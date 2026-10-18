import { createContext, PropsWithChildren, useContext, useState, useEffect } from 'react'

type DockerMcpCatalog = {
  ref: string;
  source: string;
  title: string;
  digest: string;
  servers: Array<DockerMcpCatalogRecord>;
}

type DockerMcpCatalogRecord = {
  type: string // image or remote
  image?: string
  endpoint?: string
  snapshot: { server: DockerMcpCatalogServerDef }
}

export type DockerMcpCatalogServerDef = {
  name: string;
  type: string;
  image?: string;
  remote?: {
    url: string;
    transport_type: string;
  };
  title?: string;
  description?: string;
  icon?: string;
  readme?: string;
  metadata?: any;
  [key: string]: any;
}

type DockerMcpCatalogContextType = {
  catalog: DockerMcpCatalog;
  getServerDef: (name: string) => DockerMcpCatalogServerDef;
}

const DockerMcpCatalogContext = createContext<DockerMcpCatalogContextType | null>(null)


export const DockerMcpCatalogProvider = ({ children }: PropsWithChildren) => {
  //const mcpCatalog = mcpCatalogData as DockerMcpCatalog;
  const [mcpCatalog, setMcpCatalog] = useState<DockerMcpCatalog>()

  const getServerDef = (name: string): DockerMcpCatalogServerDef => {
    if (!mcpCatalog) {
      console.warn('MCP Catalog not loaded yet')
      return null
    }
    const record = mcpCatalog.servers.find((record) => record.snapshot.server.name===name)
    return record?.snapshot.server
  }

  const contextValue = {
    catalog: mcpCatalog,
    getServerDef,
  }

  const fetchCatalog = async () => {
    try {
      const response = await fetch('/assets/docker-mcp-catalog-oci.json')
      if (!response.ok) {
        throw new Error(`Failed to fetch MCP catalog: ${response.statusText}`)
      }
      const data = await response.json()
      setMcpCatalog(data)
    } catch (error) {
      console.error('Error fetching MCP catalog:', error)
    }
  }

  useEffect(() => {
    fetchCatalog()
  }, [])

  return <DockerMcpCatalogContext.Provider value={contextValue}>
    {children}
  </DockerMcpCatalogContext.Provider>
}

export const useDockerMcpCatalog = () => {
  const context = useContext(DockerMcpCatalogContext)
  if (!context) {
    throw new Error('useDockerMcpCatalog must be used within DockerMcpCatalogProvider')
  }
  return context
}
