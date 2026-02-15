import React, { PropsWithChildren } from 'react'
import TauriPanel from './TauriPanel.tsx'
import { TauriPanelProvider } from '@/components/tauri/TauriPanelContext.tsx'

const TauriWrapper = (props: PropsWithChildren) => {
  return (
    <div className={'TauriWrapper'}>
      {props.children}
      <TauriPanel />
    </div>
  )
}

export default TauriWrapper