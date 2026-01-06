import React from 'react'
import AppSocket from '@/app-socket.tsx'

const WsChat = () => {
  return (
    <div>
      <h1>WebSocket Chat Component</h1>
      <AppSocket />
    </div>
  )
}

export default WsChat