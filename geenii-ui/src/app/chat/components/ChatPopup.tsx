import React from 'react'
import Popup from '../../../components/Popup.tsx'
import ChatContextProvider from './ChatContextProvider.tsx'
import CompletionChat from '../completion-chat.tsx'

const ChatPopup = ({ show, onClose}) => {
  const handleClose = () => {
    if (onClose) {
      onClose()
    }
  }

  return (
    <>
      {/* Popup for Quick Completion */}
      <Popup show={show} onClose={handleClose} title="Chat" size="md"
             showCloseButton={true}>
        <div>
          <ChatContextProvider>
            <CompletionChat />
          </ChatContextProvider>
        </div>
      </Popup>
    </>
  )
}

export default ChatPopup
