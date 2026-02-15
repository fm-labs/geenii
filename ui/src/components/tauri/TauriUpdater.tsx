import React from 'react'
import { Button } from '../../ui'
import { check, Update } from '@tauri-apps/plugin-updater'
import { relaunch } from '@tauri-apps/plugin-process'
import { RefreshCcwDot } from 'lucide-react'

const TauriUpdater = () => {

  //const [isChecking, setIsChecking] = React.useState(false)
  //const [isUpdating, setIsUpdating] = React.useState(false)
  const [updateInfo, setUpdateInfo] = React.useState<Update|null>(null)
  const [updateStatus, setUpdateStatus] = React.useState<string>('')

  const handleCheckUpdate = async () => {
    //setIsChecking(true)
    setUpdateInfo(null)
    setUpdateStatus("Checking for updates...")
    const update: Update | null = await check()
      .then((update) => {
        if (update) {
          console.log(
            `found update`, update,
          )
          setUpdateStatus("Update available")
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
      //.finally(() => setIsChecking(false))
    setUpdateInfo(update)
  }

  const handleUpdate = async () => {
    //setIsChecking(true)
    setUpdateInfo(null)
    setUpdateStatus("Checking for updates...")
    const update: Update | null = await check()
      .catch((e) => {
        console.error('Error checking for updates:', e)
        return null
      })
      //.finally(() => setIsChecking(false))
    //setIsChecking(false)

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
    //setIsUpdating(true)
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
      //setIsUpdating(false)
      setUpdateStatus("Finished")
    })

    console.log('update installed')
    //await relaunch()
  }

  return (
    <div>

      {/*<Button onClick={handleCheckUpdate}>Check for updates</Button>*/}

      <div className={'flex space-x-1 justify-self-start text-sm'}>
        <div>
          <RefreshCcwDot size={16} onClick={handleCheckUpdate} />
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

export default TauriUpdater