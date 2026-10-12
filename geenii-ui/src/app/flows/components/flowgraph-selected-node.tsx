import React from 'react'
import { useFlowgraph } from '@/app/flows/components/flowgraph-provider.tsx'

const FlowgraphSelectedNode = () => {
  const { nodes, selectedNodeId } = useFlowgraph()

  const selectedNode = React.useMemo(() => {
    console.log("Selected Node ID changed:", selectedNodeId)
    return nodes.find(node => node.id === selectedNodeId) || null
  }, [nodes, selectedNodeId])

  return (
    <div>
      {selectedNode ? (
        <div>
          <h3 className={"font-bold text-lg"}>Selected Node</h3>
          <p><strong>ID:</strong> {selectedNode.id}</p>
          <p><strong>Type:</strong> {selectedNode.type}</p>
          <p><strong>Label:</strong> {selectedNode.label}</p>
          <pre><strong>Metadata:</strong> {JSON.stringify(selectedNode.metadata, null, 2)}</pre>
        </div>
      ) : (
        <p>No node selected</p>
      )}
    </div>
  )
}

export default FlowgraphSelectedNode