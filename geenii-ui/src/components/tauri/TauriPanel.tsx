import React from 'react'
import { AppContext } from '../../context/app-context.tsx'
import TauriUpdaterPanelItem from '@/components/tauri/TauriUpdaterPanelItem.tsx'
import TauriServerPanelItem from '@/components/tauri/TauriServerPanelItem.tsx'
import TauriSettingsPanelItem from '@/components/tauri/TauriSettingsPanelItem.tsx'
import { TauriPanelProvider, useTauriPanel } from '@/components/tauri/TauriPanelContext.tsx'

const TauriPanel = () => {
  const { isTauri, apiInfo } = React.useContext(AppContext)

  if (!isTauri) {
    return null // Don't render anything if not in Tauri environment
  }

  return (
    <TauriPanelProvider>
      <div className={'TauriPanel fixed w-full left-0 bottom-0 p-2 pe-3'} style={{zIndex: 10000 }}>
        <div className={'flex items-center gap-1 justify-end text-sm'}>
          <TauriServerPanelItem />
          <TauriUpdaterPanelItem />
          {/*<TauriSettingsPanelItem />*/}
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
