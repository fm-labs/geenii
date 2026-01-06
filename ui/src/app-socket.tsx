import React from 'react'
import { toast } from 'react-toastify'
import { Button } from '@/components/ui/button.tsx'
import { Textarea } from '@/components/ui/textarea.tsx'
import {
  ApprovalChatMessageContent,
  ChatMessage,
  ChatMessageContent,
  FunctionPermissionChatMessageContent,
} from '@/app/chat/components/chat.types.ts'
import { convo } from '@/convo.ts'

const APP_SOCKET_URL = 'ws://localhost:13030/ws'


const useWebSocket = (url: string) => {
  const wsRef = React.useRef(null);
  const [socketConnected, setSocketConnected] = React.useState(false)
  const [messages, setMessages] = React.useState<string[]>([])

  const rpcQueue = React.useRef<Map<string, (result: any) => void>>(new Map())

  const RPC_CALL_TIMEOUT = 20000; // 30 seconds

  const rpcCall = (method: string, params: any) => {
    if (wsRef.current && socketConnected) {
      const request = {
        jsonrpc: '2.0',
        method,
        params,
        id: Date.now() + Math.random().toString(16).slice(2)
      }
      const message = JSON.stringify(request)
      wsRef.current.send(message)
      setMessages((prevMessages) => [...prevMessages, '[tx]' + message])
      // Return a promise that resolves when the response is received
      const p = new Promise<any>((resolve, reject) => {
        rpcQueue.current.set(request.id, resolve)
        console.log("Enqueued RPC call:", request)
        // Timeout to reject the promise if no response is received
        setTimeout(() => {
          if (rpcQueue.current.has(request.id)) {
            rpcQueue.current.delete(request.id)
            reject(new Error('RPC call timed out'))
          }
        }, RPC_CALL_TIMEOUT)
      })
      return toast.promise(
        p,
        {
          pending: `RPC call "${method}" in progress...`,
          success: `RPC call "${method}" succeeded!`,
          error: `RPC call "${method}" failed!`
        }
      )
    } else {
      console.error('WebSocket is not connected')
    }
  }

  const rpcNotify = (method: string, params: any) => {
    if (wsRef.current && socketConnected) {
      const request = {
        jsonrpc: '2.0',
        method,
        params
      }
      const message = JSON.stringify(request)
      wsRef.current.send(message)
      setMessages((prevMessages) => [...prevMessages, '[tx]' + message])
    } else {
      console.error('WebSocket is not connected')
    }
  }

  React.useEffect(() => {
    console.log("Connecting to WebSocket:", url)
    const ws = new WebSocket(url)
    wsRef.current = ws;
    ws.onopen = (e) => {
      console.log('WebSocket connected', e)
      setSocketConnected(true)
      const request = {
        jsonrpc: '2.0',
        method: 'hello'
      }
      const message = JSON.stringify(request)
      wsRef.current.send(message)
      setMessages((prevMessages) => [...prevMessages, '[tx]' + message])
    }

    ws.onmessage = (event) => {
      const message = event.data
      console.log('WebSocket message received:', message)
      setMessages((prevMessages) => [...prevMessages, '[rx]' + message])

      // Handle RPC responses
      try {
        const data = JSON.parse(message)
        if (data?.jsonrpc === '2.0') {
          if (data.id && rpcQueue.current.has(data.id)) {
            const resolve = rpcQueue.current.get(data.id)
            resolve(data.result)
            rpcQueue.current.delete(data.id)
            console.log("Resolved RPC call:", data)
          }
        } else if (data?.type === "event") {
          console.log("Received event:", data)
        } else if (data?.type === "notification") {
          console.log("Received notification:", data)
          toast.info(data?.payload)
        }
      } catch (error) {
        console.error("Error parsing WebSocket message:", error)
      }
    }

    ws.onclose = (event) => {
      if (event.wasClean) {
        console.log(`WebSocket connection closed cleanly, code=${event.code} reason=${event.reason}`)
      } else {
        console.log('WebSocket connection died')
      }
      setSocketConnected(false)
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
      setSocketConnected(false)
    }

    return () => {
      ws.close();
    }
  }, [url])

  return { ws: wsRef.current, socketConnected, messages, rpcCall, rpcNotify }
}



const AppSocket = () => {
  const token = 'test-token-123'
  const url = APP_SOCKET_URL + `?token=${token}`
  const { ws, socketConnected, messages, rpcCall, rpcNotify } = useWebSocket(url)
  const [inputValue, setInputValue] = React.useState("")
  const [conversation, setConversation] = React.useState<ChatMessage[]>(convo)

  const chatId = "default-chat"

  const messageHandler = (message: string) => {

  }

  const handleSubmit = async () => {
    if (ws && socketConnected) {
      const result = await rpcCall("chat/message", { chatId, input: inputValue})
      setInputValue("")

    } else {
      console.error('WebSocket is not connected')
    }
  }

  const renderContentPart = (part: ChatMessageContent, partIndex: number) => {
    if (part.type === 'text') {
      return <div key={partIndex} className={"whitespace-pre-wrap border p-2"}>{part.text}</div>
    } else if (part.type === 'code') {
      return <pre key={partIndex} className={"p-2 rounded border border-white overflow-x-auto mb-1"}><code>{part.text}</code></pre>
    } else if (part.type === 'image') {
      if (part?.data?.url) {
        return <img key={partIndex} src={part.data.url} alt="Image" className={"max-w-full h-auto"} />
      }
      else if (part?.data?.url) {
        return <img key={partIndex} src={part.data.base64} alt="Image" className={"max-w-full h-auto"} />
      }
    } else if (part.type === 'function') {
      return <div key={partIndex} className={"p-2 border border-blue-800 rounded"}>
        <strong>Function Call:</strong> {part.function?.name}({JSON.stringify(part.function?.args)})
      </div>
    } else if (part.type === 'function_permission') {
      const permPart = part as FunctionPermissionChatMessageContent
      return <div key={partIndex} className={"p-2 border border-orange-700 rounded"}>
        <strong>Function Permission:</strong> {permPart.function?.name}({JSON.stringify(permPart.function?.args)}) - <em>{permPart.text} ({permPart?.data?.approved ? "Approved" : "Denied"})</em>
      </div>
    } else if (part.type === 'approval' && part.data.scope === 'REQUEST') {
      const approvalPart = part as ApprovalChatMessageContent
      return <div key={partIndex} className={"p-2 border border-red-900 rounded"}>
        <strong>Approval ({approvalPart.data.scope}):</strong> {approvalPart.text}
        <Button>Approve</Button>
        <Button>Deny</Button>
      </div>
    } else if (part.type === 'approval' && part.data.scope === 'RESPONSE') {
      const approvalPart = part as ApprovalChatMessageContent
      return <div key={partIndex} className={"p-2 border border-red-900 rounded"}>
        <strong>Approval ({approvalPart.data.scope}):</strong> {approvalPart.text}
      </div>
    } else {
      return <p key={partIndex}>[Unsupported content type: {part.type}]</p>
    }
  }

  return (
    <div className={"overflow-y-auto p-4 border-gray-300 rounded max-w-200 mx-auto"}>

      <div>
        <strong>Chat:</strong>
        <div className={"flex flex-col items-center justify-center"}>
          {conversation.map((msg, index) => (
            <div key={index} className={`mb-4 ${msg.role === 'user' ? 'self-end' : 'self-start'}`}>
              {msg.content.map((part, partIndex) => <div className={"mb-2"}>
                {renderContentPart(part, partIndex)}
              </div>)}
            </div>
          ))}
        </div>
      </div>

      {/*<Input type="text" value={inputValue} onChange={(e) => setInputValue(e.target.value)} className={"mb-2 w-full"} />*/}
      <Textarea rows={5} value={inputValue} onChange={(e) => setInputValue(e.target.value)} className={"mb-2 w-full"} />
      <Button onClick={() => {}}>Send</Button>
      <hr />
      <div>
        <strong>WebSocket Status:</strong> {socketConnected ? <span className={"text-green-600"}>Connected</span> : <span className={"text-red-600"}>Disconnected</span>}
      </div>
      <div className={"mb-2"}>
        <Button onClick={() => rpcCall('ping', {})}>Send Ping</Button>
        <Button onClick={() => rpcCall('echo', {})}>Send Echo</Button>
        <Button onClick={() => rpcCall('sleep', {timeout: 10})}>Long Running (10)</Button>
        <Button onClick={() => rpcCall('sleep', {timeout: 30})}>Long Running (30)</Button>
        <Button onClick={() => rpcCall('ai/completion', {prompt: "tell me a joke", model: "ollama:mistral:latest"})}>Completion Ollama</Button>
        <Button onClick={() => rpcCall('ai/completion', {prompt: "tell me a joke", model: "openai:gpt-4o-mini"})}>Completion OpenAI</Button>
        <Button onClick={() => rpcCall('topics/subscribe', {topic: "demo-events"})}>Subscribe</Button>
        <Button onClick={() => rpcCall('topics/unsubscribe', {topic: "demo-events"})}>Unsubscribe</Button>
        <Button onClick={() => rpcCall('topics/publish', {topic: "demo-events", "message": `This is a test message at ${Date.now()}`})}>Publish</Button>
        <Button onClick={() => rpcCall('topics/publish', {topic: "demo-events", "message": JSON.stringify({"text": `This is a test message at ${Date.now()}`})})}>Publish dict</Button>
      </div>

      <div>
        <strong>Messages:</strong>
        <ul className={"list-disc list-inside"}>
          {messages.map((msg, index) => (
            <li key={index} className={"break-all"}>{msg}</li>
          ))}
        </ul>
      </div>
    </div>
  )
}

export default AppSocket