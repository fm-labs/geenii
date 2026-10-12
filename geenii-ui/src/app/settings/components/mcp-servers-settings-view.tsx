import * as React from 'react'
import { McpServersProvider, useMcpServers } from '@/app/mcp-servers/components/mcp-servers-provider.tsx'
import { DockerMcpCatalogProvider } from '@/app/mcp-servers/components/docker-mcp-catalog-provider.tsx'
import DockerMcpCatalog from '@/app/mcp-servers/components/docker-mcp-catalog.tsx'
import { McpServer } from '@/app/mcp-servers/components/mcp-server.tsx'
import { McpServerProvider } from '@/app/mcp-servers/components/mcp-server-provider.tsx'

const McpServersAdminView = () => {
  const { servers } = useMcpServers()
  const [selectedServerName, setSelectedServerName] = React.useState<string | null>(null)

  return <div>
    {servers && servers.map((server) => (
      <div key={server.name} className="p-4 mb-4 border rounded-2xl">
        <h3 className="text-xl font-semibold mb-2" onClick={() => setSelectedServerName(server.name)}>{server.name}</h3>
        {selectedServerName && server.name === selectedServerName && <div>
          <McpServerProvider serverName={server.name} server={server}>
            <McpServer />
          </McpServerProvider>
        </div>}
      </div>
    ))}
  </div>
}
export const McpServersSettingsView = () => {
  return <div>
    <h2 className="text-2xl font-bold mb-4">Installed MCP Servers</h2>
    <p className="text-gray-600 mb-4">
      Manage your MCP Servers settings here.
    </p>
    <McpServersProvider>
      <McpServersAdminView />
    </McpServersProvider>

    <h2 className="text-2xl font-bold mb-4">MCP Server Catalog</h2>
    <p className="text-gray-600 mb-4">
      Browse and install MCP Servers from the Docker MCP Catalog.
    </p>
    <DockerMcpCatalogProvider>
      <DockerMcpCatalog />
    </DockerMcpCatalogProvider>
  </div>
}