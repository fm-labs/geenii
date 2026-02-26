import React from 'react'
import TauriAppViewer from '@/app/apps/tauri-app-viewer.tsx'
import Header from '@/components/header.tsx'
import Layout from '@/components/layout/layout.tsx'
import { useRoute } from '@/app-router.tsx'
import { NotFoundError } from '@/features/errors/not-found-error.tsx'

const AppPage = () => {

  // const queryDict = Object.fromEntries(new URLSearchParams(window.location.search))
  // console.log(">> AppsPage query params", queryDict)
  // const initialAppId = queryDict['app'] || null
  const route = useRoute()
  console.log('route', route)

  const initialAppId = route?.params?.appId || null
  const [appId, setAppId] = React.useState<string|null>(initialAppId)

  if (!appId) {
    return <NotFoundError />
  }

  return (
    <Layout>
      <div className={"p-4"}>
        <Header title={appId}>
          {/*<select value={appId} onChange={(e) => setAppId(e.target.value)}>
            <option value={''}>-- Select App --</option>
            {APP_IDS.map((id) => (
              <option key={id} value={id}>{id}</option>
            ))}
          </select>*/}
        </Header>
        {appId && <TauriAppViewer appId={appId} />}
      </div>
    </Layout>
  )
}

export default AppPage