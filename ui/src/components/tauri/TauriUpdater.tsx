import React from 'react'
import { Button } from '../../ui'
import { check, Update } from '@tauri-apps/plugin-updater'
import { relaunch } from '@tauri-apps/plugin-process'

const TauriUpdater = () => {

  const [isChecking, setIsChecking] = React.useState(false)
  const [isUpdating, setIsUpdating] = React.useState(false)
  const [updateInfo, setUpdateInfo] = React.useState<Update|null>(null)
  const [updateStatus, setUpdateStatus] = React.useState<string>('')

  const handleCheckUpdate = async () => {
    setIsChecking(true)
    setUpdateInfo(null)
    setUpdateStatus("")
    const update: Update | null = await check()
      .then((update) => {
        if (update) {
          console.log(
            `found update`, update,
          )
        } else {
          console.log('no update found')
        }
        return update
      })
      .catch((e) => {
        console.error('Error checking for updates:', e)
        return null
      })
      .finally(() => setIsChecking(false))
    setUpdateInfo(update)
  }

  const handleUpdate = async () => {

    setIsChecking(true)
    const update: Update | null = await check()
      .catch((e) => {
        console.error('Error checking for updates:', e)
        return null
      })
      .finally(() => setIsChecking(false))
    setIsChecking(false)

    if (!update) {
      console.log('no update found')
      return
    }

    console.log(
      `found update ${update.version} from ${update.date} with notes ${update.body}`,
    )
    let downloaded = 0
    let contentLength = 0

    // alternatively we could also call update.download() and update.install() separately
    setIsUpdating(true)
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
      setIsUpdating(false)
      setUpdateStatus("Finished")
    })

    console.log('update installed')
    //await relaunch()
  }

  return (
    <div>
      <Button onClick={handleCheckUpdate}>Check for updates</Button>

      {isChecking && <p>Checking for updates...</p>}

      {updateInfo && (
        <div>
          <p>Update found: {updateInfo.version}</p>
          <Button onClick={handleUpdate} disabled={isUpdating}>
            {isUpdating ? 'Updating...' : 'Update now'}
          </Button>
          {isUpdating && <p>{updateStatus}</p>}
        </div>
      )}

      {updateInfo && updateStatus === "Finished" && (
        <div>
          <p>Update installed successfully. Please restart the application to apply the update.</p>
          <Button onClick={() => relaunch()}>Relaunch</Button>
        </div>
      )}
    </div>
  )
}

export default TauriUpdater