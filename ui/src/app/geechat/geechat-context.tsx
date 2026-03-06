import { ChatMessage } from '@/app/geechat/geechat-types.ts'
import React from 'react'
import { EXAMPLE_MESSAGES } from '@/app/geechat/geechat-example-messages.ts'
import { XAI_API_URL } from '@/constants.ts'


type GeeChatContextType = {
  messages: ChatMessage[];
  setMessages: (messages: ChatMessage[]) => void;
  addMessage: (message: ChatMessage) => void;
  roomId: string;
  username: string;
}


export const GeeChatContext = React.createContext<GeeChatContextType | null>(null)


export const GeeChatContextProvider: React.FC<{ children: React.ReactNode, username: string, roomId: string }> = ({ children, username, roomId }) => {

  const [messages, setMessages] = React.useState<ChatMessage[]>(roomId === "example_room" ? EXAMPLE_MESSAGES : [])
  const [lastUpdatedTimestampMs, setLastUpdatedTimestampMs] = React.useState<number>(0)

  const addMessage = (message: ChatMessage) => {
    console.log('Adding message to context:', message)
    setMessages(prevMessages => [...prevMessages, message])
  }

  const fetchMessages = React.useCallback(async () => {
    try {
      const response = await fetch(XAI_API_URL + `api/v1/chat/rooms/${roomId}/messages?after=${lastUpdatedTimestampMs}`)
      if (response.ok) {
        const data = await response.json()
        console.log('Fetched messages:', data)
        if (data && data.length > 0) {
          if (lastUpdatedTimestampMs) {
            data.forEach((msg: ChatMessage) => {
              addMessage(msg)
            })
          } else {
            setMessages(data)
          }
          const nowTimestampMs = Date.now()
          setLastUpdatedTimestampMs(nowTimestampMs)
          console.log(`Updated lastUpdatedTimestampMs to ${nowTimestampMs} after fetching ${data.length} messages`)
        }
      } else {
        console.error('Failed to fetch messages:', response.statusText)
      }
    } catch (error) {
      console.error('Error fetching messages:', error)
    }
  }, [roomId, lastUpdatedTimestampMs])

  React.useEffect(() => {
    if (!roomId) {
      console.warn('No roomId provided, skipping message fetch')
      return
    }
    fetchMessages()

    // Set up polling to fetch new messages every few seconds
    const intervalId = setInterval(fetchMessages, 5000) // fetch new messages every 5 seconds

    return () => clearInterval(intervalId) // clean up on unmount
  }, [roomId, lastUpdatedTimestampMs])

  return (
    <GeeChatContext.Provider value={{ messages, setMessages, addMessage, username, roomId }}>
      {children}
    </GeeChatContext.Provider>
  )
}