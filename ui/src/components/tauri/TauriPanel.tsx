import React from 'react'
import { AppContext } from '../../context/AppContext.tsx'
import TauriUpdaterPanelItem from '@/components/tauri/TauriUpdaterPanelItem.tsx'
import TauriSettingsPanelItem from '@/components/tauri/TauriSettingsPanelItem.tsx'
import TauriAppInfoPanelItem from '@/components/tauri/TauriAppInfoPanelItem.tsx'
import { TauriPanelProvider, useTauriPanel } from '@/components/tauri/TauriPanelContext.tsx'

const TauriPanel = () => {
  const { isTauri, apiInfo } = React.useContext(AppContext)

  if (!isTauri) {
    return null // Don't render anything if not in Tauri environment
  }

  return (
    <TauriPanelProvider>
      <div className={'TauriPanel fixed w-full left-0 bottom-0 p-2 pe-3'} style={{zIndex: 10000 }}>
        <div className={'flex space-x-2 justify-end text-sm'}>
          <TauriAppInfoPanelItem />
          <TauriUpdaterPanelItem />
          <TauriSettingsPanelItem />
        </div>
      </div>
      <TauriPanelBody />
    </TauriPanelProvider>
  )
}

const TauriPanelBody = () => {
  const { body, isOpen } = useTauriPanel()

  if (!isOpen) {
    return null
  }

  return (
    <div className={'TauriPanelBody fixed w-full max-h-full overflow-y-scroll left-0 bottom-12 p-4 bg-accent'} style={{zIndex: 11000 }}>
      {body}
    </div>
  )
}

export default TauriPanel
