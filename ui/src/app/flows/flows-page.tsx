import React from 'react'
import Layout from '@/components/layout/layout.tsx'
import MainContent from '@/components/layout/main-content.tsx'
import Header from '@/components/header.tsx'
import { Button } from '@/components/ui/button.tsx'

//import flowData from './data/example-flow1.json'
import JsonView from "@/components/json-view.tsx";
import { FlowgraphProvider } from '@/app/flows/components/flowgraph-provider.tsx'
import FlowgraphCanvas from '@/app/flows/components/flowgraph-canvas.tsx'
import FlowgraphBackground from '@/app/flows/components/flowgraph-background.tsx'
import FlowgraphNodes from '@/app/flows/components/flowgraph-nodes.tsx'
import { FlowgraphNodeType } from '@/app/flows/components/flowgraph-types.ts'
import FlowgraphEdges from '@/app/flows/components/flowgraph-edges.tsx'
import FlowgraphEditorPanel from '@/app/flows/components/flowgraph-editor-panel.tsx'
import FlowgraphEditor from '@/app/flows/components/flowgraph-editor.tsx'
import FlowgraphSelectedNode from '@/app/flows/components/flowgraph-selected-node.tsx'

const FlowsPage = () => {
  const [flowData, setFlowData] = React.useState<any>(null)

  if (!flowData) {
    // Load flow data from local JSON file
    // React.useEffect(() => {
    //   fetch('/flows/data/example-flow1.json')
    //     .then(response => response.json())
    //     .then(data => setFlowData(data))
    //     .catch(error => console.error('Error loading flow data:', error))
    // }, [])
    //
    // return <div>Loading flow data...</div>

    return <div>Not implemented yet :)</div>
  }

  return (
    <div>
        <FlowgraphProvider nodes={flowData.nodes as FlowgraphNodeType[]} edges={flowData.edges}>
          <div className={"flex flex-col h-screen w-screen"}>
            <header className={"bg-accent"}>
              <FlowgraphEditorPanel />
            </header>
            <div className={"flex flex-row flex-1 overflow-hidden"}>
              <main className={"relative w-7xl flex-1"}>
                <FlowgraphCanvas>
                  <FlowgraphEditor />
                  <FlowgraphBackground />
                  <FlowgraphNodes />
                  <FlowgraphEdges />
                </FlowgraphCanvas>
                <JsonView src={flowData} collapsed={true} />
              </main>
              <aside style={{width: "300px"}} className={"bg-accent w-[300px] p-2"}>
                <FlowgraphSelectedNode />
              </aside>
            </div>
          </div>
        </FlowgraphProvider>
    </div>
  )
}

export default FlowsPage