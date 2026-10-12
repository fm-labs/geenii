
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
    inputSchema?: any
    outputSchema?: any
    icons?: any
    annotations?: any
    _meta?: any
}
