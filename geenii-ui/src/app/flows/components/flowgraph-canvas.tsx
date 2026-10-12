import React from 'react'
import './flowgraph.scss'
import { useFlowgraph } from '@/app/flows/components/flowgraph-provider.tsx'

type FlowgraphCanvasContextType = {
  containerRef?: React.RefObject<HTMLDivElement>
  canvasRef: React.RefObject<HTMLDivElement>,
  nodeRefs: Record<string, React.RefObject<HTMLDivElement>>,
  edgeRefs: Record<string, React.RefObject<SVGSVGElement>>,

  newConnection: { fromNodeId: string, fromNodePort: string, startX: number, startY: number, endX: number, endY: number } | null,
  setNewConnection: React.Dispatch<React.SetStateAction<{ fromNodeId: string, fromNodePort: string, startX: number, startY: number, endX: number, endY: number } | null>>,
}

const FlowgraphCanvasContext = React.createContext<FlowgraphCanvasContextType | null>(null)

export const useFlowgraphCanvas = () => {
  const context = React.useContext(FlowgraphCanvasContext)
  if (!context) {
    throw new Error('useFlowgraphCanvas must be used within a FlowgraphCanvasProvider')
  }
  return context
}

const FlowgraphCanvas = (props: React.PropsWithChildren<any>) => {
  const { nodes, edges } = useFlowgraph()

  const [newConnection, setNewConnection] = React.useState<{ fromNodeId: string, fromNodePort: string, startX: number, startY: number, endX: number, endY: number } | null>(null)
  //const [dragOffset, setDragOffset] = React.useState<{ x: number, y: number }>({ x: 0, y: 0 })

  const nodeRefs: Record<string, React.RefObject<HTMLDivElement>> = React.useMemo(() => {
    const refs: Record<string, React.RefObject<HTMLDivElement>> = {}
    nodes.forEach(node => {
      refs[node.id] = React.createRef<HTMLDivElement>()
    })
    return refs
  }, [nodes])

  const edgeRefs: Record<string, React.RefObject<SVGSVGElement>> = React.useMemo(() => {
    const refs: Record<string, React.RefObject<SVGSVGElement>> = {}
    edges.forEach(edge => {
      const key = `${edge.from_node}->${edge.to_node}`
      refs[key] = React.createRef<SVGSVGElement>()
    })
    return refs
  }, [edges])

  const canvasRef: React.RefObject<HTMLDivElement> = React.useRef<HTMLDivElement>(null)

  const containerStyle = {
    width: '100%',
    height: '100%',
    overflow: 'auto' as const,
    position: 'relative' as const,
    border: '1px solid #ccc',
    borderRadius: '8px',
    backgroundColor: '#ffffff',
  }
  const containerRef = React.useRef<HTMLDivElement>(null)

  const canvasStyle = {
    width: '3000px',
    height: '3000px',
    //backgroundColor: '#f0f0f0',
    position: 'relative' as const,
  }

  const canvasContextValue = {
    containerRef,
    canvasRef,
    nodeRefs,
    edgeRefs,
    newConnection,
    setNewConnection,
  }

  return (
    <FlowgraphCanvasContext.Provider value={canvasContextValue}>
      <div className={"flowgraph-canvas-container"} ref={containerRef} style={containerStyle}>
        <div className="flowgraph-canvas" ref={canvasRef} style={canvasStyle}>
          {props.children}
        </div>
      </div>
    </FlowgraphCanvasContext.Provider>
  )
}

export default FlowgraphCanvas