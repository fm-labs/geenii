
export type FlowgraphNodeType = {
  id: string
  type: string
  label: string
  metadata?: {
    position: {
      x: number
      y: number
    }
  },
  properties?: Record<string, any>,
}

export type FlowgraphEdgeType = {
  from_node: string
  from_port: string
  to_node: string
  to_port: string
  metadata?: any
}