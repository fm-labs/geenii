import React from 'react'
import Popup from '../../ui/Popup.tsx'
import { AppContext } from '../../context/AppContext.tsx'
import SettingsView from './SettingsView.tsx'

const SettingsPopup = ({ show, onClose}) => {
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
      <Popup show={show} onClose={handleClose} title="Settings" size="xl"
             showCloseButton={true}>
        <div>
          <h2 className="text-xl font-semibold mb-4">Settings</h2>
          <p className="text-gray-600 mb-4">
            App settings allow you to configure various aspects of the application, such as model preferences,
            API keys, and other options. Adjust these settings to tailor the app to your needs.
          </p>
          <SettingsView />
        </div>
      </Popup>
    </>
  )
}

export default SettingsPopup
