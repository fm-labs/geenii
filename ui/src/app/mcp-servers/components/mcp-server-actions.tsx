import React, { useState } from 'react'
import Button from '@/ui/Button.tsx'
import McpServerToolForm from '@/app/mcp-servers/components/mcp-server-tool-form.tsx'
import JsonView from "@/components/json-view.tsx";
import { useMcpServer } from '@/app/mcp-servers/components/mcp-server-provider.tsx'

const McpServerActions = () => {
  const { serverName, server, tools, fetchTools } = useMcpServer();
  const [selectedTool, setSelectedTool] = useState<McpServerTool | null>(null);

  return (
    <div>
      <div>
        <Button onClick={fetchTools}>List actions</Button>
      </div>
      {tools && tools.length > 0 && tools.map((tool: McpServerTool) => (
        <div key={tool?.name} className={"mb-2"} onClick={() => setSelectedTool(tool)}>
          <span className={"font-bold"}>{tool.name}:</span>
          <p>{tool.description}</p>

          {selectedTool && selectedTool.name === tool.name && (
            <div className={"_bg-accent"}>
              <McpServerToolForm tool={tool} />
              <JsonView src={tool} collapsed={true} theme={"apathy"} />
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

export default McpServerActions