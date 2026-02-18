import React, { useCallback } from "react";
import Form from "@rjsf/shadcn";
import validator from "@rjsf/validator-ajv8";
import { useMcpServer } from "@/app/mcp-servers/components/mcp-server-provider.tsx";
import JsonView from "@/components/json-view.tsx";

const McpServerToolForm = ({ tool }: { tool: McpServerTool }) => {
    const { callTool } = useMcpServer();
    const [result, setResult] = React.useState<any>()

    const handleSubmit = React.useCallback(async (form: any) => {
        const data = form?.formData || {};
        console.log(data);
        try {
            const result = await callTool(tool.name, data);
            setResult(result);
        } catch (error) {
            console.error(error);
        }
    }, [callTool, tool.name, setResult]);

    return (
        <div>
            <Form schema={tool?.inputSchema}
                  validator={validator}
                  onSubmit={handleSubmit}
            />
            {result && <JsonView src={result} />}
        </div>
    );
};

export default McpServerToolForm;
