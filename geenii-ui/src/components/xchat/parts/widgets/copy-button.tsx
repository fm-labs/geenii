import React from 'react'
import { CheckIcon, CopyIcon } from 'lucide-react'
import { Button } from '@/components/ui/button.tsx'

/** Small "Copy" button for widget headers; shows "Copied" for a moment after copying */
export const CopyButton = ({ text }: { text: string }) => {
  const [copied, setCopied] = React.useState(false)
  const copy = async () => {
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }
  return (
    <Button variant={'ghost'} size={'sm'} className={'h-6 px-2'} onClick={copy}>
      {copied ? <CheckIcon /> : <CopyIcon />}{copied ? 'Copied' : 'Copy'}
    </Button>
  )
}
