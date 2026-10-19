
type McpServer = {
    name: string;
    type?: string
    url?: string;
    command?: string;
    args?: string[];
    env?: {
        [key: string]: string;
    }
}

type McpServerTool = {
    name: string;
    description?: string;
    title?: string;
    input_schema?: any
    output_schema?: any
    icons?: any
    annotations?: any
    meta?: any
}

/** One `mcpServers` entry in mcp.json (fastmcp server config plus geenii's `legacy` flag) */
type McpServerConfig = {
    // stdio
    command?: string;
    args?: string[];
    env?: { [key: string]: string };
    cwd?: string;
    // remote
    url?: string;
    transport?: 'stdio' | 'http' | 'streamable-http' | 'sse';
    headers?: { [key: string]: string };
    // common
    type?: string;
    description?: string;
    timeout?: number;
    legacy?: boolean;
    [key: string]: any;
}
