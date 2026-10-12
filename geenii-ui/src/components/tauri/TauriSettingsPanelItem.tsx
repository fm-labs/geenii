import { SettingsIcon } from 'lucide-react'
import React from 'react'
import { useTauriPanel } from '@/components/tauri/TauriPanelContext.tsx'
import TauriCommands from '@/components/tauri/TauriCommands.tsx'

const TauriSettingsPanelItem = () => {
  const { setBody, setIsOpen, isOpen } = useTauriPanel()

  const handleSettings = () => {
    if (isOpen) {
      setIsOpen(false)
      setBody(null)
      return
    }

    setBody(<div>
      <TauriCommands />
    </div>)
    setIsOpen(true)
  }

  return (
    <div title={'Manage App Settings'} className={'cursor-pointer'}>
      <SettingsIcon size={16} onClick={handleSettings} />
    </div>
  )
}

export default TauriSettingsPanelItem