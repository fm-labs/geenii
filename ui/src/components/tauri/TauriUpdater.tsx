import React from 'react'
import { Button } from '../../ui'
import { check, Update } from '@tauri-apps/plugin-updater'
import { relaunch } from '@tauri-apps/plugin-process'

const TauriUpdater = () => {

  const [isChecking, setIsChecking] = React.useState(false)
  const [isUpdating, setIsUpdating] = React.useState(false)
  const [updateInfo, setUpdateInfo] = React.useState<Update|null>(null)

  const handleCheckUpdate = async () => {
    setIsChecking(true)
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
          break
        case 'Progress':
          downloaded += event.data.chunkLength
          console.log(`downloaded ${downloaded} from ${contentLength}`)
          break
        case 'Finished':
          console.log('download finished')
          break
      }
    }).finally(() => setIsUpdating(false))

    console.log('update installed')
    await relaunch()

  }

  return (
    <div>
      <Button onClick={handleCheckUpdate}>Check for updates</Button>
      <Button onClick={handleUpdate}>Update</Button>
    </div>
  )
}

export default TauriUpdater