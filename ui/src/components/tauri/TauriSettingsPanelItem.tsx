import { SettingsIcon } from 'lucide-react'
import React from 'react'
import { useTauriPanel } from '@/components/tauri/TauriPanelContext.tsx'
import TauriSystemInfo from '@/components/tauri/TauriSystemInfo.tsx'

const TauriSettingsPanelItem = () => {
  const { setBody, setIsOpen, isOpen } = useTauriPanel()

  const handleSettings = () => {
    if (isOpen) {
      setIsOpen(false)
      setBody(null)
      return
    }

    // This function can be used to open a settings dialog or perform other actions
    console.log('Settings clicked')
    //notify.info("settings clicked")
    setBody(<div>
      <TauriSystemInfo />
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