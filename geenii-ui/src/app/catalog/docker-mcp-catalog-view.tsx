import * as React from 'react'
import { DockerMcpCatalogProvider } from '@/app/catalog/components/docker-mcp-catalog-provider.tsx'
import DockerMcpCatalogOci from '@/app/catalog/components/docker-mcp-catalog-oci.tsx'

export const DockerMcpCatalogView = () => {
  return <div>
    <h2 className="text-2xl font-bold mb-4">MCP Server Catalog</h2>
    <p className="text-gray-600 mb-4">
      Browse and install MCP Servers from the Docker MCP Catalog.
    </p>

    <DockerMcpCatalogProvider>
      <DockerMcpCatalogOci />
    </DockerMcpCatalogProvider>

    {/*<DockerMcpCatalogV3Provider>*/}
    {/*  <DockerMcpCatalogV3 />*/}
    {/*</DockerMcpCatalogV3Provider>*/}
  </div>
}
