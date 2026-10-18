import * as React from 'react'
import { DockerMcpCatalogProvider } from '@/app/mcp-servers/components/docker-mcp-catalog-provider.tsx'
import DockerMcpCatalog from '@/app/mcp-servers/components/docker-mcp-catalog.tsx'

export const McpServersDockerView = () => {
  return <div>
    <h2 className="text-2xl font-bold mb-4">MCP Server Catalog</h2>
    <p className="text-gray-600 mb-4">
      Browse and install MCP Servers from the Docker MCP Catalog.
    </p>
    <DockerMcpCatalogProvider>
      <DockerMcpCatalog />
    </DockerMcpCatalogProvider>
  </div>
}
