import React from 'react'
import { ExternalLinkIcon, GlobeIcon } from 'lucide-react'
import { Button } from '@/components/ui/button.tsx'
import { WidgetRendererProps } from '@/components/xchat/chat.types.ts'

type IframeData = { url: string; scripts?: boolean; trusted?: boolean; height?: number; title?: string }

/** The url if it is http(s), else null (no javascript:, data:, file: …) */
const safeUrl = (url?: string): URL | null => {
  try {
    const parsed = new URL(url ?? '', window.location.href)
    return parsed.protocol === 'http:' || parsed.protocol === 'https:' ? parsed : null
  } catch {
    return null
  }
}

/**
 * Sandbox flags. Without `scripts` the page is static. With `scripts` a cross-origin page keeps its own
 * origin (cookies, storage), but a same-origin page does not: scripts plus same-origin could lift the sandbox.
 */
const sandboxFor = (url: URL, scripts: boolean) => {
  if (!scripts) return ''
  const flags = ['allow-scripts', 'allow-forms', 'allow-popups', 'allow-popups-to-escape-sandbox']
  if (url.origin !== window.location.origin) flags.push('allow-same-origin')
  return flags.join(' ')
}

/**
 * geenii.iframe — data: { url, scripts? = false, trusted? = false, height? = 320, title? }
 * Untrusted pages load only after a click; `scripts` allows scripts in the (sandboxed) frame.
 */
export const IframeWidget = ({ data }: WidgetRendererProps<IframeData | null>) => {
  const url = safeUrl(data?.url)
  const [loaded, setLoaded] = React.useState(!!data?.trusted)
  const height = data?.height ?? 320

  if (!url) return <div className={'text-sm text-muted-foreground italic'}>[iframe: invalid url {data?.url}]</div>

  return (
    <div className={'rounded-md border overflow-hidden'}>
      <div className={'flex items-center justify-between gap-2 bg-muted px-3 py-1 text-xs text-muted-foreground'}>
        <span className={'truncate'} title={url.href}>{data?.title || url.host + url.pathname}</span>
        <Button variant={'ghost'} size={'sm'} className={'h-6 px-2'} asChild>
          <a href={url.href} target={'_blank'} rel={'noopener noreferrer'}>
            <ExternalLinkIcon />Open
          </a>
        </Button>
      </div>
      {loaded ? (
        <iframe
          src={url.href}
          sandbox={sandboxFor(url, !!data?.scripts)}
          referrerPolicy={'no-referrer'}
          title={data?.title ?? url.host}
          style={{ height }}
          className={'block w-full bg-white'}
        />
      ) : (
        <div style={{ height }} className={'flex flex-col items-center justify-center gap-2 p-4 text-center text-sm'}>
          <GlobeIcon className={'size-6 text-muted-foreground'} />
          <div className={'text-muted-foreground'}>
            Load content from <span className={'font-medium text-foreground'}>{url.host}</span>?
            {data?.scripts && <div className={'text-xs'}>The page may run scripts.</div>}
          </div>
          <Button variant={'outline'} size={'sm'} onClick={() => setLoaded(true)}>Load</Button>
        </div>
      )}
    </div>
  )
}
