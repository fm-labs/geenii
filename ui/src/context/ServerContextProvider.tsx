import React, { PropsWithChildren } from 'react'
import { ServerContext } from './ServerContext.tsx'
import { XAI_API_URL } from '../constants.ts'
import { ServerIcon } from 'lucide-react'

const ServerContextProvider = (props: PropsWithChildren) => {
  const [serverUrl, setServerUrl] = React.useState<string>(XAI_API_URL)
  const [connected, setConnected] = React.useState<boolean>(true)

  const serverContext = {
    serverUrl,
    setServerUrl
  }

  if (!serverUrl || !connected) {
    return (
      <div className={"p-10"}>
        <h2 className="text-2xl font-bold mb-4">Server Configuration</h2>
        <p className="mb-2">Please configure the server URL:</p>
        <input
          type="text"
          value={serverUrl}
          onChange={(e) => setServerUrl(e.target.value)}
          placeholder="Enter server URL"
          className="border p-2 w-full mb-4"
        />
        <button
          onClick={() => setConnected(true)}
          className="bg-blue-500 text-white px-4 py-2 rounded"
        >
          Connect
        </button>
      </div>
    )
  }

  return (
    <ServerContext.Provider value={serverContext}>
      {props.children}
      <div className={"fixed bottom-0 left-0 w-full bg-accent p-1 shadow-md opacity-80 hover:opacity-100 transition-opacity flex space-x-2 align-middle"}>
        <div className="text-sm text-gray-500 flex space-x-2">{" "}Server: {serverUrl}</div>
      </div>
    </ServerContext.Provider>
  )
}

export default ServerContextProvider
