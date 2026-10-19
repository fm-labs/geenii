/** Agent spec as returned by GET /api/v1/agents/ */
export type AgentType = {
  name: string;
  file_path?: string;
  model?: string | null;
  label?: string | null;
  description?: string | null;
  system?: string | null;
  tools?: string[];
  skills?: string[];
  model_parameters?: Record<string, any>;
  mcp_servers?: string[];
  class_name?: string | null;
  /** Set from the directory the spec was loaded from */
  scope?: 'global' | 'project' | 'user';
  working_dir?: string | null;
  allowed_dirs?: string[] | null;
}

/** GET /api/v1/agents/{name}: the spec plus the markdown body of the spec file */
export type AgentDetailType = AgentType & {
  instructions?: string;
}

/** GET /api/v1/agents/{name}/commands: built-in commands, then one per configured skill */
export type AgentCommandType = {
  command: string;
  description: string;
}

/** Strip the "mcp__<server>__" prefix from MCP tool names for display. */
export const shortToolName = (tool: string) => {
  const match = tool.match(/^mcp__.+?__(.+)$/)
  return match ? match[1] : tool
}

/** The MCP server an "mcp__<server>__<tool>" tool belongs to, or null for other tools. */
export const mcpServerOfTool = (tool: string) => {
  const match = tool.match(/^mcp__(.+?)__.+$/)
  return match ? match[1] : null
}

export const agentUrl = (name: string) => `#/agents/${encodeURIComponent(name)}`
