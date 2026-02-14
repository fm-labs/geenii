import React, { PropsWithChildren } from 'react'
import { useFlowgraphCanvas } from '@/app/flows/components/flowgraph-canvas.tsx'
import { useFlowgraph } from '@/app/flows/components/flowgraph-provider.tsx'
import { buildPathD } from '@/app/flows/components/svgutil.ts'

const FlowgraphEditor = (props: PropsWithChildren<any>) => {
  const { nodes, edges, updateNodePosition } = useFlowgraph()
  const { canvasRef, nodeRefs, edgeRefs, newConnection } = useFlowgraphCanvas()

  React.useEffect(() => {
    console.log('FlowgraphEditor mounted')

    return () => {
      console.log('FlowgraphEditor unmounted')
    }
  })

  const svgPath = React.useMemo(() => {
    if (!newConnection) return null;
    const x1 = newConnection.startX
    const y1 = newConnection.startY
    const x2 = newConnection.endX
    const y2 = newConnection.endY
    //const midX = (x1 + x2) / 2;
    //const d = `M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`;
    //return d;
    return buildPathD(x1, y1, x2, y2, {kind: 'curved'});
  }, [newConnection])



  return (
    <div className={"absolute"}>
      {newConnection && svgPath && (
        <svg
          ref={edgeRefs[`temp-connection`]}
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            width: '100%',
            height: '100%',
            pointerEvents: 'none',
          }}
        >
          {/*<line
            x1={newConnection.startX}
            y1={newConnection.startY}
            x2={newConnection.endX}
            y2={newConnection.endY}
            stroke="blue"
            strokeWidth={2}
            stroke-dasharray="12 10"
          />*/}
          <path d={svgPath}
                fill="none"
                stroke="black"
                stroke-width="2"
                stroke-linecap="round"
                stroke-dasharray="12 10">
            <animate attributeName="stroke-dashoffset"
                     values="0; -44"
                     dur="1s"
                     repeatCount="indefinite" />
          </path>
        </svg>
      )}
    </div>
  )
}

export default FlowgraphEditor