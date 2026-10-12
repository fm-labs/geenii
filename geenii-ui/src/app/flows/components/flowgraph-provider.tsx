import React from 'react'
import { FlowgraphEdgeType, FlowgraphNodeType } from '@/app/flows/components/flowgraph-types.ts'

type FlowgraphContextType = {
  nodes: FlowgraphNodeType[],
  setNodes: React.Dispatch<React.SetStateAction<FlowgraphNodeType[]>>,
  edges: FlowgraphEdgeType[],
  setEdges: React.Dispatch<React.SetStateAction<FlowgraphEdgeType[]>>,
  addNode: (node: FlowgraphNodeType) => Promise<void>,
  updateNode: (node: FlowgraphNodeType) => Promise<void>,
  updateNodePosition: (nodeId: string, position: { x: number, y: number }) => Promise<void>,
  getNodeById: (nodeId: string) => FlowgraphNodeType | undefined,
  addEdge: (edge: FlowgraphEdgeType) => Promise<void>,
  removeEdge: (edge: FlowgraphEdgeType) => Promise<void>,
  removeNode: (nodeId: string) => Promise<void>,
  saveFlowgraph: () => Promise<void>,
  loadFlowgraph: (data: { nodes: FlowgraphNodeType[], edges: FlowgraphEdgeType[] }) => Promise<void>,
  uploadFlowgraph: (file: File) => Promise<void>,

  selectedNodeId: string | null,
  setSelectedNodeId: React.Dispatch<React.SetStateAction<string | null>>,
}

export const FlowgraphContext = React.createContext<FlowgraphContextType | null>(null)

export const FlowgraphProvider: React.FC<React.PropsWithChildren<{nodes: FlowgraphNodeType[], edges: any[]}>> = ({ children, nodes: initialNodes, edges: initialEdges }) => {

  const [nodes, setNodes] = React.useState<FlowgraphNodeType[]>(initialNodes)
  const [edges, setEdges] = React.useState<any[]>(initialEdges)

  const [selectedNodeId, setSelectedNodeId] = React.useState<string | null>(null)

  const addNode = async (node: FlowgraphNodeType) => {
    setNodes(prev => [...prev, node])
  }

  const updateNode = async (updatedNode: FlowgraphNodeType) => {
    setNodes(prev => prev.map(n => n.id === updatedNode.id ? updatedNode : n))
  }

  const updateNodePosition = async (nodeId: string, position: { x: number, y: number }) => {
    setNodes(prev => prev.map(n => {
      if (n.id === nodeId) {
        return {
          ...n,
          metadata: {
            ...n.metadata,
            position,
          }
        }
      }
      return n
    }))
  }

  const getNodeById = (nodeId: string) => {
    return nodes.find(n => n.id === nodeId)
  }

  const addEdge = async (edge: FlowgraphEdgeType) => {
    setEdges(prev => [...prev, edge])
  }

  const removeEdge = async (edge: FlowgraphEdgeType) => {
    setEdges(prev => prev.filter(e => e.from_node !== edge.from_node || e.to_node !== edge.to_node))
  }

  const removeNode = async (nodeId: string) => {
    setNodes(prev => prev.filter(n => n.id !== nodeId))
    setEdges(prev => prev.filter(e => e.source !== nodeId && e.target !== nodeId))
  }

  const saveFlowgraph = async () => {
    // Implement saving logic here, e.g., send to backend or save to local storage
    console.log('Saving flowgraph...', { nodes, edges })

    const flowData = { nodes, edges };
    const dataStr = JSON.stringify(flowData, null, 2);
    const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr);

    const exportFileDefaultName = 'flow.json';

    const linkElement = document.createElement('a');
    linkElement.setAttribute('href', dataUri);
    linkElement.setAttribute('download', exportFileDefaultName);
    linkElement.click();
  }

  const loadFlowgraph = async (data: { nodes: FlowgraphNodeType[], edges: FlowgraphEdgeType[] }) => {
    setNodes(data.nodes)
    setEdges(data.edges)
  }

  const uploadFlowgraph = async (file: File) => {
    const reader = new FileReader();
    reader.onload = (event) => {
      if (event.target?.result) {
        const content = event.target.result as string;
        try {
          const data = JSON.parse(content);
          loadFlowgraph(data);
        } catch (error) {
          console.error('Error parsing flowgraph JSON:', error);
        }
      }
    };
    reader.readAsText(file);
  }

  const contextValue = React.useMemo(() => {
    return {
      nodes,
      edges,
      setNodes,
      setEdges,
      addNode,
      getNodeById,
      updateNode,
      updateNodePosition,
      addEdge,
      removeEdge,
      removeNode,
      saveFlowgraph,
      loadFlowgraph,
      uploadFlowgraph,
      selectedNodeId,
      setSelectedNodeId,
    }
  }, [nodes, edges, selectedNodeId])

  React.useEffect(() => {
    console.log("Selected Node ID changed:", selectedNodeId)
  }, [selectedNodeId])

  return (
    <FlowgraphContext.Provider value={contextValue}>
      {children}
    </FlowgraphContext.Provider>
  )
}

export const useFlowgraph = () => {
  const context = React.useContext(FlowgraphContext)
  if (!context) {
    throw new Error('useFlowgraph must be used within a FlowgraphProvider')
  }
  return context
}