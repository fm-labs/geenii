import React, { useCallback } from 'react'
import Layout from '@/components/layout/layout.tsx'
import MainContent from '@/components/layout/main-content.tsx'
import Header from '@/components/header.tsx'
import { Button } from '@/components/ui/button.tsx'
import { XAI_API_URL } from '@/constants.ts'
import { PlaySquareIcon } from 'lucide-react'
import { SchemaFormDialog } from '@/components/form/schema-form-dialog.tsx'
import useNotification from '@/hooks/useNotification.ts'

type Tool = {
  name: string;
  description: string;
  parameters: object;
}

const ToolCard = ({ tool }: { tool: Tool }) => {
  const notify = useNotification()

  const [showDialog, setShowDialog] = React.useState(false)
  const [isExecuting, setIsExecuting] = React.useState(false)
  const [executionResult, setExecutionResult] = React.useState<any>(null)

  const handleExecute = () => {
    // Implement tool execution logic here
    console.log(`Executing tool: ${tool.name}`)
    setShowDialog(true)
  }

  const handleSubmit = async ({ formData }) => {
    console.log("Submitting tool execution with data:", formData)
    try {
      setIsExecuting(true)
      const response = await fetch(XAI_API_URL + `api/v1/tools/${tool.name}/execute`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(formData)
      })
      if (response.ok) {
        const result = await response.json()
        console.log("Tool execution result:", result)
        // Handle successful execution result (e.g., show a success message or display results)
        setExecutionResult(result)
        notify.success("Tool executed successfully.")
      } else {
        console.error("Failed to execute tool:", response.statusText)
        notify.error(`Failed to execute tool: ${response.statusText}`)
      }
    } catch (error) {
      console.error("Error executing tool:", error)
      notify.error(error)
    } finally {
      setIsExecuting(false)
      setShowDialog(false)
    }
  }

  return (
    <div className={"border rounded p-4 mb-4"}>
      <h2 className={"text-lg font-bold mb-2"}>{tool.name}</h2>
      <div className={"flex flex-wrap justify-between"}>
        <p className={"text-gray-600 mb-2"}>{tool.description}</p>
        <div>
          <Button onClick={handleExecute}><PlaySquareIcon /> Execute</Button>
        </div>
      </div>

      {/*<pre className={"bg-accent p-2 rounded text-sm overflow-x-auto"}>
        {JSON.stringify(tool.parameters, null, 2)}
      </pre>*/}

      {showDialog && (
        <SchemaFormDialog schema={tool.parameters}
                          dialogTitle={`${tool.name} ${isExecuting ? 'Executing ...' : ''}`}
                          onChange={async (values) => console.log("Parameters changed", values)}
                          onSubmit={handleSubmit}
                          open={showDialog}
                          onOpenChange={() => setShowDialog(false)} />
      )}

      <div>
        {executionResult && (
          <div className={"mt-4 p-2 border rounded bg-green-50"}>
            <h3 className={"font-bold mb-2"}>Execution Result:</h3>
            <pre className={"text-sm overflow-x-auto"}>
              {JSON.stringify(executionResult, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  )
}



const ToolsPage = () => {

  const [tools, setTools] = React.useState<Tool[]>([]);

  const fetchTools = useCallback(async () => {
    try {
      const response = await fetch(XAI_API_URL + `api/v1/tools`)
      if (response.ok) {
        const data = await response.json()
        console.log(data)
        setTools(data);
      } else {
        console.error("Failed to fetch tools:", response.statusText)
      }
    } catch (error) {
      console.error("Error fetching tools:", error)
      setTools([]);
    }
  }, [setTools])

  React.useEffect(() => {
    fetchTools()
  }, [fetchTools])
  
  return (
    <Layout>
      <MainContent>
        <Header title={"Tools"} subtitle={"Tools can be used by agentic wizards to perform actions or retrieve information."}>
          {/*<Button>Refresh</Button>*/}
        </Header>

        {tools.map((tool) => (
          <ToolCard key={tool.name} tool={tool} />
        ))}
      </MainContent>
    </Layout>
  )
}

export default ToolsPage