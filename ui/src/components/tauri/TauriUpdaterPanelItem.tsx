import React from 'react'
import { check, Update } from '@tauri-apps/plugin-updater'
import { relaunch } from '@tauri-apps/plugin-process'
import { RefreshCcwDot } from 'lucide-react'
import useNotification from '@/hooks/useNotification.ts'
import { TAURI_UPDATER_CHECK_INTERVAL } from '@/constants.ts'
import "@/Animate.scss"

const sleep = async (ms: number) => new Promise(resolve => setTimeout(resolve, ms))

const TauriUpdaterPanelItem = () => {
  const notify = useNotification()

  const [updateInfo, setUpdateInfo] = React.useState<Update|null>(null)
  const [updateStatus, setUpdateStatus] = React.useState<string>('')

  const handleCheckUpdate = async () => {
    setUpdateInfo(null)
    setUpdateStatus("Checking for updates...")
    await sleep(3000)

    const update: Update | null = await check()
      .then((update) => {
        if (update) {
          console.log(
            `found update`, update,
          )
          setUpdateStatus("Update available")
          notify.info(`A new app version is available: ${update.version}`)
        } else {
          console.log('no update found')
          setUpdateStatus("")
        }
        return update
      })
      .catch((e) => {
        console.error('Error checking for updates:', e)
        return null
      })
    setUpdateInfo(update)
  }

  const handleUpdate = async () => {
    setUpdateInfo(null)
    setUpdateStatus("Checking for updates...")
    const update: Update | null = await check()
      .catch((e) => {
        console.error('Error checking for updates:', e)
        return null
      })

    if (!update) {
      console.log('no update found')
      return
    }

    setUpdateInfo(update)
    console.log(
      `found update ${update.version} from ${update.date} with notes ${update.body}`,
    )
    let downloaded = 0
    let contentLength = 0

    // alternatively we could also call update.download() and update.install() separately
    setUpdateStatus("Updating...")
    await update.downloadAndInstall((event) => {
      switch (event.event) {
        case 'Started':
          contentLength = event.data.contentLength
          console.log(`started downloading ${event.data.contentLength} bytes`)
          setUpdateStatus("Downloading...")
          break
        case 'Progress':
          downloaded += event.data.chunkLength
          console.log(`downloaded ${downloaded} from ${contentLength}`)
          setUpdateStatus("Downloading... " + Math.round((downloaded / contentLength) * 100) + "%")
          break
        case 'Finished':
          console.log('download finished')
          setUpdateStatus("Download finished, installing...")
          break
      }
    }).finally(() => {
      setUpdateStatus("Finished")
    })

    console.log('update installed')
    //await relaunch()
  }

  React.useEffect(() => {
    handleCheckUpdate() // check for updates on mount

    const interval = setInterval(() => {
      handleCheckUpdate()
    }, TAURI_UPDATER_CHECK_INTERVAL)

    return () => clearInterval(interval)
  }, []);

  const getIconClass = () => {
    switch (updateStatus) {
      case "Checking for updates...":
        return "animate-spin"
      case "Update available":
        return "text-yellow-500 animate-pulse"
      case "Updating...":
      case "Downloading...":
        return "text-orange-500 animate-spin"
      case "Finished":
        return "text-green-500"
      default:
        return ""
    }
  }

  return (
    <div>
      <div className={'flex space-x-1 justify-self-start text-sm'}>
        <div title={'Check for updates'} className={"cursor-pointer hover:bg-accent rounded"} >
          <RefreshCcwDot size={16} onClick={handleCheckUpdate} className={getIconClass()} />
        </div>

        <div>{updateStatus}</div>

        {updateInfo && (
          <div>
            {updateStatus === "Update available" &&
              <span className={"cursor-pointer hover:bg-accent"} onClick={handleUpdate} title={`Update available: ${updateInfo.version}`}>[Install]</span>}
          </div>
        )}

        {updateInfo && updateStatus === "Finished" && (
          <div>
            <span className={"cursor-pointer hover:bg-accent"} onClick={() => relaunch()}>[Restart App]</span>
          </div>
        )}
      </div>
    </div>
  )
}

export default TauriUpdaterPanelItem