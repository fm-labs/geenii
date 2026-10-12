import React from 'react'
import Header from '@/components/header.tsx'
import MainContent from '@/components/layout/main-content.tsx'
import { McpServerProvider } from '@/app/mcp-servers/components/mcp-server-provider.tsx'
import { McpServersProvider, useMcpServers } from '@/app/mcp-servers/components/mcp-servers-provider.tsx'
import { McpServer } from '@/app/mcp-servers/components/mcp-server.tsx'
import Layout from '@/components/layout/layout.tsx'
import { Button } from '@/components/ui/button.tsx'
import { McpServersView } from '@/app/mcp-servers/mcp-servers-view.tsx'

const McpServers = () => {
  const { servers } = useMcpServers()

  return <div>
    {servers && Object.entries(servers).map(([name, server]) => (
      <McpServerProvider key={name} server={server} serverName={name}>
        <McpServer />
      </McpServerProvider>
    ))}
  </div>
}

const McpServersPage = () => {
  return (
    <Layout>
      <>
        {/*<Header title="MCP Servers" subtitle="Manage your MCP Servers here">
          <Button asChild>
            <a href="#/mcp/docker">View Docker MCP Catalog</a>
          </Button>
        </Header>*/}
        <McpServersProvider>
          <McpServersView />
        </McpServersProvider>
      </>
    </Layout>
  )
}

export default McpServersPage
