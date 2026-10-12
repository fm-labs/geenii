import React from 'react'
import ReactJson, { ReactJsonViewProps } from '@microlink/react-json-view'

type JsonViewProps = ReactJsonViewProps & {
  src: any;
  collapsed?: boolean;
}

const JsonDebugView = ({src, collapsed, ...props}: JsonViewProps) => {
  return (
    <div className={"rounded-md border bg-muted p-2 overflow-auto mb-2 max-h-100"}>
      <ReactJson src={src}
                 collapsed={collapsed}
                 displayDataTypes={false}
                 displayObjectSize={false}
                 displayArrayKey={false}
                 quotesOnKeys={false}
                 theme={"twilight"}
                 enableClipboard={false}
                 {...props} />
    </div>
  )
}

export default JsonDebugView