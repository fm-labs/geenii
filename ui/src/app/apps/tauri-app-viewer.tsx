import React from 'react'

import { invoke } from '@tauri-apps/api/core'
import { Button } from '@/components/ui/button.tsx'
import { AppContext } from '@/context/AppContext.tsx'

//import { open } from "@tauri-apps/plugin-dialog";


export async function registerApp(appName: string): Promise<string> {
  const siteId = await invoke<string>("register_app", { appName: appName });
  console.info(`Registered app ${appName} with siteId ${siteId}`)
  return siteId
}

export async function requestIframeUrlForSite(siteId: string): Promise<string> {
  console.info(`Requesting iframe url for siteId ${siteId}`)
  return await invoke<string>("get_site_iframe_url", { siteId })
}

export async function openSiteWindow(siteId: string): Promise<string> {
  console.info(`Opening window for siteId ${siteId}`)
  return await invoke<string>("open_site_window", { siteId })
}

const buildTauriAppAuthToken = (appId: string, siteId: string, userId: string): string => {
  // For now, we'll just create a simple token with the necessary info encoded in it.
  // @todo: generate signed token on the backend.
  const payload = {
    app: appId,
    aud: siteId,
    sub: userId,
    exp: Math.floor(Date.now() / 1000) + (60 * 60), // Token expires in 1 hour
  }
  return btoa(JSON.stringify(payload))
}

const TauriAppViewer = ({appId}: {appId}) => {
  const {isTauri} = React.useContext(AppContext)

  const userId = "user-123" // dummy user id for now
  const [siteId, setSiteId] = React.useState<string>(null)
  const [iframeUrl, setIframeUrl] = React.useState<string>(null)

  if (!isTauri) {
    return (
      <div>
        <p>This view is only available in the Tauri desktop version.</p>
      </div>
    )
  }

  const handleOpenAppIframe = React.useCallback(async () => {
    let _siteId = siteId
    if (!_siteId) {
      _siteId = await registerApp(appId)
      setSiteId(_siteId)
    }
    const iframeUrl = await requestIframeUrlForSite(_siteId)
    const query = {
      t: buildTauriAppAuthToken(appId, _siteId, userId),
    }
    const urlWithQuery = new URL(iframeUrl)
    Object.keys(query).forEach(key => urlWithQuery.searchParams.append(key, query[key]))
    setIframeUrl(urlWithQuery.toString())
  },  [appId])

  const handleOpenAppWindow = React.useCallback(async (e) => {
    let _siteId = siteId
    if (!_siteId) {
      _siteId = await registerApp(appId)
      setSiteId(_siteId)
    }
    await openSiteWindow(_siteId)

    e.preventDefault()
    e.stopPropagation()
    return
  }, [appId])

  React.useEffect(() => {
    // Automatically open the app in an iframe when the component mounts
    handleOpenAppIframe().then(() => {
      console.info("App iframe opened successfully", appId)
    }). catch((error) => {
      console.error("Error opening app iframe:", appId, error)
    })
  }, [appId])

  return (
    <div className={""}>
      {/*<div className={"p-2 space-x-1 flex"}>
        <Button variant={"default"} size={"sm"} onClick={handleOpenAppWindow}>Open in new window</Button>
        <Button variant={"default"} size={"sm"} onClick={handleOpenAppIframe}>Open in iframe</Button>
      </div>*/}
      <div className={"text-right text-sm text-foreground-muted mb-2"}>
        <span onClick={handleOpenAppWindow} className={"hover:cursor-pointer"}>Open in new window</span>
      </div>
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