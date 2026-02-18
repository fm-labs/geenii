import React from 'react'
import ReactJson, { ReactJsonViewProps } from '@microlink/react-json-view'

type JsonViewProps = ReactJsonViewProps & {
  src: any;
  collapsed?: boolean;
}

const JsonView = ({src, collapsed, ...props}: JsonViewProps) => {
  return (
    <div className={"rounded-md border bg-muted p-2 overflow-auto mb-2"}>
      <ReactJson src={src}
                 collapsed={collapsed}
                 displayDataTypes={false}
                 displayObjectSize={false}
                 displayArrayKey={false}
                 quotesOnKeys={false}
                 theme={"twilight"}
                 {...props} />
    </div>
  )
}

export default JsonView