import React from 'react'

import { invoke } from '@tauri-apps/api/core'
import { Button } from '@/components/ui/button.tsx'
import { AppContext } from '@/context/AppContext.tsx'

//import { open } from "@tauri-apps/plugin-dialog";

export async function openFolderAsSite(dir: string) {
  //const dir = await open({ directory: true, multiple: false });
  if (!dir || Array.isArray(dir)) return;

  const siteId = await invoke<string>("register_site_root", { rootDir: dir });
  await invoke("open_site_window", { siteId });
}

export async function requestIframeUrlForApp(appId: string): Promise<string> {
  const dir = `/Users/phil/workspaces/fmlabs/geenii/.geenii/apps/${appId}`
  const siteId = await invoke<string>("register_site_root", { rootDir: dir });
  //const iframeUrl = `site://localhost/${siteId}/index.html`
  return await invoke<string>("get_site_iframe_url", { siteId })
}

const TauriAppViewer = ({appId}: {appId}) => {
  const {isTauri} = React.useContext(AppContext)

  const [iframeUrl, setIframeUrl] = React.useState<string>(null)

  if (!isTauri) {
    return (
      <div>
        <p>This view is only available in the Tauri desktop version.</p>
      </div>
    )
  }

  const handleOpenAppWindow = async () => {
    const dir = `/Users/phil/workspaces/fmlabs/geenii/.geenii/apps/${appId}`
    await openFolderAsSite(dir);
  }

  const handleOpenAppIframe = React.useCallback(async () => {
    const iframeUrl = await requestIframeUrlForApp(appId)
    setIframeUrl(iframeUrl)
  },  [appId])

  React.useEffect(() => {
    // Automatically open the app in an iframe when the component mounts
    handleOpenAppIframe()
  }, [appId])

  return (
    <div className={"border"}>
      {/*<div className={"p-2 space-x-1 flex"}>
        <Button variant={"default"} size={"sm"} onClick={handleOpenAppWindow}>Open in new window</Button>
        <Button variant={"default"} size={"sm"} onClick={handleOpenAppIframe}>Open in iframe</Button>
      </div>*/}
      {iframeUrl && (
        <iframe
          id="siteFrame"
          src={iframeUrl}
          style={{ width: '100%', height: '80vh' }}
          //className={"rounded-xl"}
          //sandbox="allow-scripts allow-forms allow-modals allow-downloads"
          allow="microphone"
          sandbox="allow-scripts allow-same-origin allow-forms allow-modals allow-downloads"
          referrerPolicy="no-referrer"
        />
      )}
    </div>
  )
}

export default TauriAppViewer