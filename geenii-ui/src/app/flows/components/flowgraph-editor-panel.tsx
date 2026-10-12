import React from 'react'
import { Button } from '@/components/ui/button.tsx'
import { useFlowgraph } from '@/app/flows/components/flowgraph-provider.tsx'

const FlowgraphEditorPanel = () => {

  const { saveFlowgraph, uploadFlowgraph, addNode } = useFlowgraph()

  const handleAddNode = async (nodeType: string) => {
    // const canvasElement = canvasRef.current
    // if (!canvasElement) {
    //   console.error('Canvas element not found')
    //   return
    // }
    // const canvasRect = canvasElement.getBoundingClientRect()
    const nodeId = `node-${Date.now()}`
    console.log('Add Node button clicked')
    const node = {
      id: nodeId,
      type: nodeType,
      label: `New ${nodeType} node`,
      inputs: [],
      outputs: [],
      metadata: {
        position: {
          x: 100 + Math.floor(Math.random() * 200),
          y: 100 + Math.floor(Math.random() * 200),
        },
      },
      properties: {} // this.getDefaultProperties(type)
    };
    await addNode(node)
  }

  const handleLoadFlow = async () => {
    // Logic to load a flow from a file or source
    console.log('Load Flow button clicked')

    // create a file input element
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = '.json'
    input.onchange = async (e: any) => {
      const file = e.target.files[0]
      await uploadFlowgraph(file)
      console.log('Upload flow graph upload successfully')
    }
    input.click()
  }

  const handleSaveFlow = async () => {
    // Logic to save the current flow to a file
    console.log('Save Flow button clicked')
    await saveFlowgraph()
  }

  return (
    <div className={"flex justify-start space-x-1 p-2"}>
      <Button onClick={() => handleAddNode('input')}>
        Add Input Node
      </Button>
      <Button onClick={() => handleAddNode('processing')}>
        Add Action Node
      </Button>
      <Button onClick={() => handleAddNode('output')}>
        Add Output Node
      </Button>
      <Button onClick={handleLoadFlow}>
        Load Flow
      </Button>
      <Button onClick={handleSaveFlow}>
        Save Flow
      </Button>
    </div>
  )
}

export default FlowgraphEditorPanel