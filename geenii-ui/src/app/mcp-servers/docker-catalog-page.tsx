import React from "react";
import MainContent from "@/components/layout/main-content.tsx";
import Header from "@/components/header.tsx";
import Layout from '@/components/layout/layout.tsx'
import { DockerMcpCatalogProvider } from '@/app/mcp-servers/components/docker-mcp-catalog-provider.tsx'
import DockerMcpCatalogOci from '@/app/mcp-servers/components/docker-mcp-catalog-oci.tsx'

const DockerCatalogPage = () => {
    return (
      <Layout>
        <MainContent>
          <Header title="Docker MCP Catalog"
                  subtitle="Safely run MCP server wrapped in docker containers" />

          <DockerMcpCatalogProvider>
            <DockerMcpCatalogOci />
          </DockerMcpCatalogProvider>

          {/*<DockerMcpCatalogV3Provider>*/}
          {/*  <DockerMcpCatalogV3 />*/}
          {/*</DockerMcpCatalogV3Provider>*/}

        </MainContent>
      </Layout>
    );
};

export default DockerCatalogPage;
