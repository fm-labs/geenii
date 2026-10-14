import React from 'react'
import { ExternalLinkIcon } from 'lucide-react'
import { WidgetRendererProps } from '@/components/xchat/chat.types.ts'
import { safeUrl } from './safe-url.ts'

type LinkItem = { title?: string; url: string; snippet?: string | null; source?: string | null }

const SHOWN = 5

/** geenii.links — data: { items: { title?, url, snippet?, source? }[], limit? = 5 }; search or web results */
export const LinksWidget = ({ data }: WidgetRendererProps<{ items: LinkItem[]; limit?: number } | null>) => {
  const items = (Array.isArray(data?.items) ? data.items : []).filter((i): i is LinkItem => typeof i?.url === 'string')
  const [all, setAll] = React.useState(false)
  const limit = data?.limit ?? SHOWN
  const shown = all ? items : items.slice(0, limit)

  return (
    <div className={'flex max-w-lg flex-col gap-3'}>
      {shown.map((item, i) => {
        const url = safeUrl(item.url)
        const title = item.title || url?.host || item.url
        return (
          <div key={i} className={'min-w-0'}>
            <div className={'truncate text-xs text-muted-foreground'}>
              {item.source || url?.host || 'invalid link'}{url && url.pathname !== '/' && <span className={'opacity-70'}>{url.pathname}</span>}
            </div>
            {url ? (
              <a href={url.href} target={'_blank'} rel={'noopener noreferrer'}
                 className={'inline-flex max-w-full items-center gap-1 font-medium hover:underline'}>
                <span className={'truncate'}>{title}</span>
                <ExternalLinkIcon className={'size-3 shrink-0 opacity-60'} />
              </a>
            ) : <div className={'font-medium'}>{title}</div>}
            {item.snippet && <div className={'line-clamp-2 text-sm text-muted-foreground'}>{item.snippet}</div>}
          </div>
        )
      })}
      {items.length > limit && (
        <button type={'button'} onClick={() => setAll((a) => !a)} className={'self-start text-xs text-muted-foreground underline'}>
          {all ? 'Show fewer' : `Show all ${items.length}`}
        </button>
      )}
    </div>
  )
}
