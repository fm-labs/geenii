import React, { PropsWithChildren } from 'react'
import TauriPanel from './TauriPanel.tsx'

const TauriWrapper = (props: PropsWithChildren) => {
  return (
    <div className={'TauriWrapper'}>
      {props.children}
      <TauriPanel />
    </div>
  )
}

export default TauriWrapper