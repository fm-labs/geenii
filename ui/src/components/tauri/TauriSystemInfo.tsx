import React from 'react'
import TauriCommandButton from '@/components/tauri/TauriCommandButton.tsx'


const TAURI_COMMANDS: any[] = [
  { label: 'echo', command: 'echo', args: ['hello', 'from', 'tauri'] },
  { label: 'docker info', command: 'docker', args: ['info', '--format', 'json'], outputFormat: 'json' },
  { label: 'docker model version', command: 'docker', args: ['model', 'version'] },
  { label: 'docker mcp version', command: 'docker', args: ['mcp', 'version'] },
  { label: 'docker mcp catalog', command: 'docker', args: ['mcp', 'catalog', 'show', 'docker-mcp'] },
  { label: 'docker mcp catalog json', command: 'docker', args: ['mcp', 'catalog', 'show', 'docker-mcp', '--format', 'json'], outputFormat: 'json' }
]

const TauriSystemInfo = () => {
  return (
    <div>
      <ul>
        {TAURI_COMMANDS.map((cmd, index) => (
          <li key={index}>
            <TauriCommandButton {...cmd} />
          </li>
        ))}
      </ul>
    </div>
  )
}

export default TauriSystemInfo