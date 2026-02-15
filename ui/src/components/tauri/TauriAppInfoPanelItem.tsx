import React from 'react'
import { AppContext } from '@/context/AppContext.tsx'
import { InfoIcon } from 'lucide-react'

const TauriAppInfoPanelItem = () => {
  const { apiInfo } = React.useContext(AppContext)

  return (
    <div>
      {apiInfo && apiInfo?.version && (
        <span title={`API version: ${apiInfo.version}`}>
          <InfoIcon size={16} />
        </span>
      )}
    </div>
  )
}

export default TauriAppInfoPanelItem