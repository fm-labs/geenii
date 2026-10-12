import React from "react";
import { DockerMcpCatalogProvider } from "@/app/mcp-servers/components/docker-mcp-catalog-provider.tsx";
import MainContent from "@/components/layout/main-content.tsx";
import Header from "@/components/header.tsx";
import DockerMcpCatalog from "@/app/mcp-servers/components/docker-mcp-catalog.tsx";
import Layout from '@/components/layout/layout.tsx'

const DockerCatalogPage = () => {
    return (
      <Layout>
        <MainContent>
          <Header title="Docker MCP Catalog"
                  subtitle="Safely run MCP server wrapped in docker containers" />
          <DockerMcpCatalogProvider>
            <DockerMcpCatalog />
          </DockerMcpCatalogProvider>
        </MainContent>
      </Layout>
    );
};

export default DockerCatalogPage;
