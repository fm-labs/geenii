import React from 'react'
import { isTauri } from '@tauri-apps/api/core'
import { openUrl } from '@tauri-apps/plugin-opener'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog.tsx'

const MESSAGE_SELECTOR = '[data-xchat-item="message"]'

/** Open a url outside the app: system browser in Tauri, a new tab on the web. */
const openExternal = async (url: string) => {
  if (isTauri()) {
    await openUrl(url)
  } else {
    window.open(url, '_blank', 'noopener,noreferrer')
  }
}

/**
 * Intercepts clicks on links inside chat messages (elements marked with data-xchat-item="message")
 * and asks the user to confirm before opening the link in a new tab.
 */
const ChatLinkGuard = ({ children }: { children: React.ReactNode }) => {
  const [pendingUrl, setPendingUrl] = React.useState<string | null>(null)

  const onClickCapture = (e: React.MouseEvent<HTMLDivElement>) => {
    const target = e.target as Element | null
    const anchor = target?.closest?.('a[href]') as HTMLAnchorElement | null
    if (!anchor || !anchor.closest(MESSAGE_SELECTOR)) return

    const href = anchor.getAttribute('href') ?? ''
    // leave in-page anchors alone
    if (href.startsWith('#')) return

    e.preventDefault()
    e.stopPropagation()
    setPendingUrl(anchor.href)
  }

  const onConfirm = () => {
    if (pendingUrl) {
      openExternal(pendingUrl).catch((err) => console.error('Failed to open link', pendingUrl, err))
    }
    setPendingUrl(null)
  }

  return (
    <div onClickCapture={onClickCapture} className={'contents'}>
      {children}
      <AlertDialog open={pendingUrl !== null} onOpenChange={(open) => !open && setPendingUrl(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Open link in new tab?</AlertDialogTitle>
            <AlertDialogDescription>
              This link will open outside the chat:
              <span className={'mt-2 block rounded bg-muted px-2 py-1 font-mono text-xs break-all text-foreground'}>
                {pendingUrl}
              </span>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={onConfirm}>Open link</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

export default ChatLinkGuard
