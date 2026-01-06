import React from 'react'
import { AppContext } from '../../context/AppContext.tsx'
import { Settings } from 'lucide-react'
import useNotification from '../../hooks/useNotification.ts'

const TAURI_COMMANDS = [
  { label: 'echo', command: 'echo', args: ['hello', 'from', 'tauri'] },
  { label: 'docker info', command: 'docker', args: ['info', '--format', 'json'], outputFormat: 'json' },
  { label: 'docker model version', command: 'docker', args: ['model', 'version'] },
  { label: 'docker mcp version', command: 'docker', args: ['mcp', 'version'] },
  { label: 'docker mcp catalog', command: 'docker', args: ['mcp', 'catalog', 'show', 'docker-mcp'] },
  { label: 'docker mcp catalog json', command: 'docker', args: ['mcp', 'catalog', 'show', 'docker-mcp', '--format', 'json'], outputFormat: 'json' }
]

const TauriPanel = () => {
  const { isTauri } = React.useContext(AppContext)
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
    <div className={'TauriPanel fixed w-full left-0 bottom-0 p-2'}>
      <div className={"flex justify-end"}>
        <Settings size={16} onClick={handleSettings} />
      </div>
    </div>
  )
}

export default TauriPanel
