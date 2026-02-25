import React from 'react'
import TauriAppViewer from '@/app/apps/tauri-app-viewer.tsx'
import Header from '@/components/header.tsx'
import Layout from '@/components/layout/layout.tsx'
import MainContent from '@/components/layout/main-content.tsx'

const APP_IDS = [ "geenii_chat", "geenii_supervisor",
  "3d_globe", "3d_rubicscube", "audio_viewer", "beep", "clock",
  "dots", "drumnbass", "hello", "hello_0", "hello_1", "hexagon", "image_editor", "mic_recorder", "pong",
  "spaceship", "todo", "trainmap", "triangle_math", "triangle_math_0"]

const AppsPage = () => {
  const [appId, setAppId] = React.useState<string>(APP_IDS[0])

  return (
    <Layout>
      <div className={"p-4"}>
        <Header title={"Apps"}>
          <select value={appId} onChange={(e) => setAppId(e.target.value)}>
            <option value={''}>-- Select App --</option>
            {APP_IDS.map((id) => (
              <option key={id} value={id}>{id}</option>
            ))}
          </select>
        </Header>
        {appId && <TauriAppViewer appId={appId} />}
      </div>
    </Layout>
  )
}

export default AppsPage