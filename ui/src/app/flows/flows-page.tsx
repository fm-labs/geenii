import React from 'react'
import Layout from '@/components/layout/layout.tsx'
import MainContent from '@/components/layout/main-content.tsx'
import Header from '@/components/header.tsx'
import { Button } from '@/components/ui/button.tsx'

import flowData from './data/example-flow.json'
import ReactJson from '@microlink/react-json-view'

const FlowsPage = () => {
  return (
    <Layout>
      <MainContent>
        <Header title={"Flows"} subtitle={"Manage your agentic workflows here"}>
          <Button>Create Workflow</Button>
        </Header>

        <div>
          {flowData?.steps.map(step => (
            <div key={step.step_id} className="border p-4 mb-2">
              <h3 className="font-bold">{step.action} - {step.step_id}</h3>
              <p>{step.name}</p>

              <pre className="p-2 rounded">
                {JSON.stringify(step, null, 2)}
              </pre>
            </div>
          ))}
        </div>

        <ReactJson src={flowData} collapsed={true} />

      </MainContent>
    </Layout>
  )
}

export default FlowsPage