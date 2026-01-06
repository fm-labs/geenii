import React from 'react'
import Popup from '../../../ui/Popup.tsx'
import { AppContext } from '../../../context/AppContext.tsx'
import ChatContextProvider from './ChatContextProvider.tsx'
import CompletionChat from '../completion-chat.tsx'

const ChatPopup = ({ show, onClose}) => {
  const context = React.useContext(AppContext)
  if (!context) {
    throw new Error('AppContext is not provided')
  }

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
