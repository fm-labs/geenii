import React from 'react'
import { useFlowgraph } from '@/app/flows/components/flowgraph-provider.tsx'
import { FlowgraphEdgeType } from '@/app/flows/components/flowgraph-types.ts'
import { useFlowgraphCanvas } from '@/app/flows/components/flowgraph-canvas.tsx'
import { buildPathD } from '@/app/flows/components/svgutil.ts'


const FlowgraphEdges = () => {
  const { edges, nodes } = useFlowgraph()
  const { nodeRefs } = useFlowgraphCanvas()

  const svgRef = React.useRef<SVGSVGElement>(null)
  const [paths, setPaths] = React.useState<Array<{ key: string, d: string }>>([])

  const computePaths = React.useCallback(() => {
    const nextPaths: Array<{ key: string, d: string }> = []

    const svg = svgRef.current;
    if (!svg) return;
    const canvasRect = svg.getBoundingClientRect();

    edges.forEach((edge: FlowgraphEdgeType) => {
      const fromEl = nodeRefs[edge.from_node]?.current
      const toEl = nodeRefs[edge.to_node]?.current

      if (!fromEl || !toEl) {
        console.warn(
          "Connection refers to non-existent node:",
          fromEl,
          toEl
        );
        return;
      }

      const fromRect = fromEl.getBoundingClientRect();
      const toRect = toEl.getBoundingClientRect();

      const x1 = fromRect.right - canvasRect.left;
      const y1 = fromRect.top + fromRect.height / 2 - canvasRect.top;
      const x2 = toRect.left - canvasRect.left;
      const y2 = toRect.top + toRect.height / 2 - canvasRect.top;

      //const midX = (x1 + x2) / 2;
      //const d = `M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`;

      const d = buildPathD(x1, y1, x2, y2, {kind: 'cubicH'});

      nextPaths.push({
        key: `${edge.from_node}->${edge.to_node}`,
        d,
      });
    });

    // // If connecting to new node while dragging, we draw a temporary line
    // if (newConnection) {
    //   console.log("Drawing temporary connection line:", newConnection)
    //   const tempFromNodeId = newConnection.fromNodeId
    //   const tempFromEl = nodeRefs[tempFromNodeId]?.current
    //   if (tempFromEl) {
    //     const fromRect = tempFromEl.getBoundingClientRect();
    //     const x1 = fromRect.right - canvasRect.left;
    //     const y1 = fromRect.top + fromRect.height / 2 - canvasRect.top;
    //
    //     // For demo purposes, we connect to mouse position (100, 100)
    //     const x2 = newConnection.endX
    //     const y2 = newConnection.endY
    //
    //     const midX = (x1 + x2) / 2;
    //     const d = `M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`;
    //
    //     nextPaths.push({
    //       key: `${tempFromNodeId}->temp`,
    //       d,
    //     });
    //   }
    // }

    setPaths(nextPaths)
  }, [nodes, edges, nodeRefs])

  React.useEffect(() => {
    computePaths()
  }, [computePaths])

  return (
    <svg
      ref={svgRef}
      id="canvas"
      style={{
        position: "absolute",
        inset: 0,
        width: "100%",
        height: "100%",
        pointerEvents: "none",
      }}
    >
      {paths.map((p) => (
        <path
          key={p.key}
          d={p.d}
          className="connection-line"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        />
      ))}
    </svg>
  )
}


// const FlowgraphEdges = () => {
//   const { edges } = useFlowgraph()
//
//   return (
//     <div className="flowgraph-edges">
//       {edges.map((edge, index) => (
//         <FlowgraphEdge key={index} edge={edge} />
//       ))}
//     </div>
//   )
// }

export default FlowgraphEdges