import React, { DragEventHandler } from 'react'
import { useFlowgraph } from '@/app/flows/components/flowgraph-provider.tsx'
import { useFlowgraphCanvas } from '@/app/flows/components/flowgraph-canvas.tsx'
import { FlowgraphNodeType } from '@/app/flows/components/flowgraph-types.ts'
import { Input } from '@/components/ui/input.tsx'


const FlowgraphNode = ({ node, ref }: { node: FlowgraphNodeType, ref: React.RefObject<HTMLDivElement> }) => {
  const { selectedNodeId, setSelectedNodeId, updateNodePosition, addEdge } = useFlowgraph()
  const { setNewConnection, newConnection, canvasRef } = useFlowgraphCanvas()

  //const ref = React.useRef<HTMLDivElement>(null)
  //const x = node?.metadata?.position.x || 0
  //const y = node?.metadata?.position.y || 0

  const onDragStart = (e: DragEvent) => {
    if (!canvasRef.current) {
      console.warn('Canvas ref not available on drag start')
      return
    }

    const rect = ref.current.getBoundingClientRect();

    const startX = e.clientX - rect.left
    const startY = e.clientY - rect.top
    console.log('Drag started (dragstart event) for node:', node.id, e, rect, { startX, startY })
    //e.dataTransfer!.setData('application/node-id', node.id)

    if (ref?.current) {
      // Optionally, set drag image or other dataTransfer properties
      //e.dataTransfer!.setDragImage(ref.current, 0, 0)
      // set the offset within the node where the drag started
      e.dataTransfer!.setData('application/drag-offset-x', String(startX))
      e.dataTransfer!.setData('application/drag-offset-y', String(startY))
    } else {
      console.warn('Node ref not available on drag start for node:', node.id)
    }
  }

  const onDragEnd = (e: DragEvent) => {

    const rect = ref.current.getBoundingClientRect();

    const startOffsetX = parseInt(e.dataTransfer!.getData('application/drag-offset-x') || '0', 10)
    const startOffsetY = parseInt(e.dataTransfer!.getData('application/drag-offset-y') || '0', 10)

    console.log('Retrieved drag offsets from dataTransfer:', { startOffsetX, startOffsetY })

    const draggedX = e.clientX - rect.left - startOffsetX
    const draggedY = e.clientY - rect.top - startOffsetY

    const endX = node?.metadata?.position.x + draggedX
    const endY = node?.metadata?.position.y + draggedY

    console.log('Drag ended (dragend event) for node:', node.id, e, {draggedX, draggedY}, { endX, endY })
    console.log('Rect on drag end:', rect)
    // Handle any cleanup if necessary
    if (ref?.current) {
      //ref.current.style.left = endX + 'px'
      //ref.current.style.top = endY + 'px'
    } else {
      console.warn('Node ref not available on drag end for node:', node.id)
    }
    updateNodePosition(node.id, { x: endX, y: endY })
  }

  const onDrag = (e: DragEvent) => {
    const rect = ref.current.getBoundingClientRect();
    const startOffsetX = parseInt(e.dataTransfer!.getData('application/drag-offset-x') || '0', 10)
    const startOffsetY = parseInt(e.dataTransfer!.getData('application/drag-offset-y') || '0', 10)

    const draggedX = e.clientX - rect.left - startOffsetX
    const draggedY = e.clientY - rect.top - startOffsetY

    const newX = node?.metadata?.position.x + draggedX
    const newY = node?.metadata?.position.y + draggedY

    //console.log('Dragging (drag event) for node:', node.id, e, { dragX, dragY })
    //await updateNodePosition(node.id, { x: dragX, y: dragY })

    // if (ref?.current) {
    //   ref.current.style.left = newX + 'px'
    //   ref.current.style.top = newY + 'px'
    // }
  }

  React.useEffect(() => {
    const element = ref.current
    if (!element) {
      console.warn('Node ref not available on initial useEffect for node:', node.id)
      return
    }

    const canvasElement = canvasRef.current
    if (!canvasElement) {
      console.warn('Canvas ref not available on initial useEffect for node:', node.id)
      return
    }

    // print element offsets
    console.log('Canvas position:', canvasElement.getBoundingClientRect())
    console.log('Node mounted with offsets:', node.id, element.getBoundingClientRect())
    console.log('Node initial position from metadata:', node.id, node?.metadata?.position)

    // let isConnecting = false
    // let connectStartX = 0
    // let connectStartY = 0

    // let isDragging = false
    // let startX = 0
    // let startY = 0

    // const onMouseDown = (e: MouseEvent) => {
    //   isDragging = true
    //   startX = e.clientX - element.offsetLeft
    //   startY = e.clientY - element.offsetTop
    //   canvasRef.current.addEventListener('mousemove', onMouseMove)
    //   canvasRef.current.addEventListener('mouseup', onMouseUp)
    //   console.log('>> Dragging started for node:', node.id, e.currentTarget)
    //   setSelectedNodeId(node.id)
    // }

    // const onMouseMove = async (e: MouseEvent) => {
    //   if (!isDragging) return
    //   const newX = e.clientX - startX
    //   const newY = e.clientY - startY
    //   console.log('>> Dragging node:', node.id, 'to position:', { x: newX, y: newY }, 'isConnecting:', !!newConnection)
    //   if (newConnection) return
    //   element.style.left = newX + 'px'
    //   element.style.top = newY + 'px'
    //   await updateNodePosition(node.id, { x: newX, y: newY })
    // }

    // const onMouseUp = async () => {
    //   isDragging = false
    //   canvasRef.current.removeEventListener('mousemove', onMouseMove)
    //   canvasRef.current.removeEventListener('mouseup', onMouseUp)
    //
    //   console.log('>> Dragging ended for node:', node.id)
    //   //console.log("New position:", { x: element.offsetLeft, y: element.offsetTop })
    //   //await updateNodePosition(node.id, { x: element.offsetLeft, y: element.offsetTop })
    //   //setNewConnection(null)
    // }

    // const onConnectionPointMouseDown = (e: MouseEvent) => {
    //   isConnecting = true
    //   connectStartX = e.clientX
    //   connectStartY = e.clientY
    //   //e.stopPropagation()
    //   //e.preventDefault()
    //   console.log(`Connection point mouse down on node:`, node.id)
    // }


    //element.addEventListener('mousedown', onMouseDown)
    //element.addEventListener('dragstart', onDragStart)
    //element.addEventListener('dragend', onDragEnd)
    //element.addEventListener('drag', onDrag)

    // element.querySelectorAll('.connection-point').forEach(cp => {
    //   cp.addEventListener('mousedown', onConnectionPointMouseDown)
    // })

    return () => {
      //element.removeEventListener('mousedown', onMouseDown)

      // element.querySelectorAll('.connection-point').forEach(cp => {
      //   cp.removeEventListener('mousedown', onConnectionPointMouseDown)
      // })
    }
  }, [])

  // const handlePointDragStart = (e: React.DragEvent<HTMLDivElement>, pointType: 'input' | 'output') => {
  //   console.log(`Drag start on ${pointType} point of node:`, node.id, e)
  //   // e.dataTransfer.setData('application/node-connection', JSON.stringify({
  //   //   nodeId: node.id,
  //   //   pointType,
  //   // }))
  //   // Optionally, set drag image or other dataTransfer properties
  // }
  //
  // const handlePointDragEnd = (e: React.DragEvent<HTMLDivElement>, pointType: 'input' | 'output') => {
  //   console.log(`Drag end on ${pointType} point of node:`, node.id, e.dataTransfer.getData('text'))
  //   // Handle any cleanup if necessary
  // }

  // const handleDoubleClick = (e: React.MouseEvent<HTMLDivElement>) => {
  //   e.stopPropagation()
  //   e.preventDefault()
  //   console.log("Node double clicked:", node.id)
  //   setSelectedNodeId(node.id)
  // }

  const handlePointDoubleClick = async (e: React.MouseEvent<HTMLDivElement>, pointType: 'input' | 'output', port: string) => {
    e.stopPropagation()
    e.preventDefault()

    const startX = e.clientX - canvasRef.current!.getBoundingClientRect().left
    const startY = e.clientY - canvasRef.current!.getBoundingClientRect().top
    console.log(`Connection point double clicked on point of node:`, node.id, { startX, startY }, e)
    //setNewConnection({ fromNodeId: node.id, startX: startX, startY: startY, endX: startX+50, endY: startY+100 })

    // If double-clicked on input point and there's an ongoing connection, complete it
    if (pointType === 'input') {
      if (newConnection) {
        // Complete the connection
        console.log('Completing connection to node:', node.id)
        const newEdge = {
          from_node: newConnection.fromNodeId,
          from_port: newConnection.fromNodePort,
          to_node: node.id,
          to_port: port,
        }
        setNewConnection(null)
        await addEdge(newEdge)
      }
      return
    } else if (pointType === 'output') {
      // If double-clicked on output point, start a new connection
      console.log('Starting new connection from node:', node.id, port)
      setNewConnection({ fromNodeId: node.id, fromNodePort: port, startX: startX, startY: startY, endX: startX, endY: startY })
    }

    // For output point, start a new connection drag

    // const onConnectingMouseMove = (moveEvent: MouseEvent) => {
    //   const endX = moveEvent.clientX - canvasRef.current!.getBoundingClientRect().left
    //   const endY = moveEvent.clientY - canvasRef.current!.getBoundingClientRect().top
    //   //setNewConnection({ fromNodeId: node.id, startX: startX, startY: startY, endX: endX, endY: endY })
    // }
    //
    // const onConnectingMouseUp = (upEvent: MouseEvent) => {
    //   console.log('Connection drag ended at:', { x: upEvent.clientX, y: upEvent.clientY }, upEvent)
    //   //const endX = upEvent.clientX - canvasRef.current!.getBoundingClientRect().left
    //   //const endY = upEvent.clientY - canvasRef.current!.getBoundingClientRect().top
    //   //setNewConnection({ fromNodeId: node.id, startX: startX, startY: startY, endX: endX, endY: endY })
    //   //setTimeout(() => setNewConnection(null), 300) // slight delay to allow edge to connect if over input point
    //
    //   canvasRef.current.removeEventListener('mousemove', onConnectingMouseMove)
    //   canvasRef.current.removeEventListener('mouseup', onConnectingMouseUp)
    // }

    //canvasRef.current.addEventListener('mousemove', onConnectingMouseMove)
    //canvasRef.current.addEventListener('mouseup', onConnectingMouseUp)
  }

  // @ts-ignore
  return (
    <div
      draggable={true}
      className={`node node-${node?.type || 'unknown'}`}
      ref={ref}
      style={{
        position: 'absolute',
        left: node?.metadata?.position.x + 'px',
        top: node?.metadata?.position.y + 'px',
        //padding: '8px',
        border: '1px solid #ccc',
        borderRadius: '4px',
        backgroundColor: '#fff',
      }}
      //onDoubleClick={handleDoubleClick}
      //@ts-ignore
      onDragStart={onDragStart}
      //@ts-ignore
      onDragEnd={onDragEnd}
      //@ts-ignore
      onDrag={onDrag}
    >
      {/*<div className={'node-drag-handle'} draggable={true}
           onDrag={(e) => console.log('drag start', e)}
           onDragEnd={(e) => console.log('drag end', e)}>☰
      </div>*/}
      <div className={'node-title'}>{node?.label || 'Unnamed Node'}</div>
      <div className={'node-content'}>
        {node?.type === 'input' && <div className={''}>
          <Input />
        </div>}
        <div className={'node-properties text-left'}>
          {node?.properties && Object.entries(node?.properties).map(([key, value]) => (
            <div key={key} className="node-property flex justify-between border">
              <div className={'relative px-2 w-full'}>
                {!key.startsWith("output") &&
                  <div className="connection-point input"
                       onDoubleClick={(e) => handlePointDoubleClick(e, 'input', key)}></div>}
                {key.startsWith("output") &&
                  <div className="connection-point output"
                       onDoubleClick={(e) => handlePointDoubleClick(e, 'output', key)}></div>}
                <strong>{key}</strong></div>
              {!key.startsWith("output") && <div>{String(value)}</div>}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

const FlowgraphNodes = () => {
  const { nodes } = useFlowgraph()
  const { nodeRefs } = useFlowgraphCanvas()

  return (
    <div className="flowgraph-nodes w-full h-full relative">
      {nodes.map((node: any) => (
        <FlowgraphNode key={node.id} ref={nodeRefs[node.id]} node={node} />
      ))}
    </div>
  )
}

export default FlowgraphNodes