import React from 'react'
import { AppContext } from '../../context/AppContext.tsx'
import { InfoIcon, Settings } from 'lucide-react'
import useNotification from '../../hooks/useNotification.ts'
import TauriUpdater from '@/components/tauri/TauriUpdater.tsx'

const TAURI_COMMANDS = [
  { label: 'echo', command: 'echo', args: ['hello', 'from', 'tauri'] },
  { label: 'docker info', command: 'docker', args: ['info', '--format', 'json'], outputFormat: 'json' },
  { label: 'docker model version', command: 'docker', args: ['model', 'version'] },
  { label: 'docker mcp version', command: 'docker', args: ['mcp', 'version'] },
  { label: 'docker mcp catalog', command: 'docker', args: ['mcp', 'catalog', 'show', 'docker-mcp'] },
  { label: 'docker mcp catalog json', command: 'docker', args: ['mcp', 'catalog', 'show', 'docker-mcp', '--format', 'json'], outputFormat: 'json' }
]

const TauriPanel = () => {
  const { isTauri, apiInfo } = React.useContext(AppContext)
  const notify = useNotification()

  if (!isTauri) {
    return null // Don't render anything if not in Tauri environment
  }

  const handleSettings = () => {
    // This function can be used to open a settings dialog or perform other actions
    console.log('Settings clicked')
    notify.info("settings clicked")
  }

  return (
    <div className={'TauriPanel fixed w-full left-0 bottom-0 p-2 pe-3'}>
      <div className={"flex space-x-1 justify-end"}>
        <InfoIcon size={16} />
        {apiInfo && apiInfo?.version && (
          <div className={"mr-4 text-sm opacity-70"}>
            v{apiInfo.version}
          </div>
        )}
        <TauriUpdater />
        <Settings size={16} onClick={handleSettings} />
      </div>
    </div>
  )
}

export default TauriPanel
