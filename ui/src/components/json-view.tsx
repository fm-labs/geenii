import React from 'react'
import ReactJson, { ReactJsonViewProps } from '@microlink/react-json-view'

type JsonViewProps = ReactJsonViewProps & {
  src: any;
  collapsed?: boolean;
}

const JsonView = ({src, collapsed, ...props}: JsonViewProps) => {
  return (
    <div className={"rounded-md border bg-muted p-2 overflow-y-scroll mb-2 max-h-100 "}>
      <pre className={"max-w-[500px]"}>{JSON.stringify(src, null, 2)}</pre>
    </div>
  )
}

export default JsonView