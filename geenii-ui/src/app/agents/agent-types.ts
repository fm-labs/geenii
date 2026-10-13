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
}
