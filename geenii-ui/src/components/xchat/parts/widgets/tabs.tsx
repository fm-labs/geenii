import React from 'react'
import { WidgetRendererProps } from '@/components/xchat/chat.types.ts'
import { ChildContent, ChildContentData } from './child-content.tsx'

type Tab = ChildContentData & { label: string }

/**
 * geenii.tabs — data: { tabs: { label, widget?: { name, data?, heading?, text? }, text? }[], active? = 0 }
 * Each tab shows a nested widget (with its own fallback and error boundary) or markdown `text`.
 * Only the active tab is mounted, so switching tabs resets the state of the widget left behind.
 */
export const TabsWidget = ({ data, message }: WidgetRendererProps<{ tabs: Tab[]; active?: number } | null>) => {
  const tabs = (Array.isArray(data?.tabs) ? data.tabs : []).filter((t): t is Tab => typeof t?.label === 'string')
  const [active, setActive] = React.useState(() => Math.min(Math.max(0, data?.active ?? 0), Math.max(0, tabs.length - 1)))
  const id = React.useId()
  const tabRefs = React.useRef<(HTMLButtonElement | null)[]>([])

  if (tabs.length === 0) return <div className={'text-sm text-muted-foreground'}>No tabs</div>
  const current = tabs[Math.min(active, tabs.length - 1)]

  // arrow keys move between tabs (WAI-ARIA tabs pattern)
  const onKeyDown = (e: React.KeyboardEvent) => {
    const step = { ArrowRight: 1, ArrowLeft: -1, Home: -active, End: tabs.length - 1 - active }[e.key]
    if (step == null) return
    e.preventDefault()
    const next = (active + step + tabs.length) % tabs.length
    setActive(next)
    tabRefs.current[next]?.focus()
  }

  return (
    <div className={'min-w-0 rounded-md border'}>
      <div role={'tablist'} onKeyDown={onKeyDown} className={'flex overflow-x-auto border-b px-1'}>
        {tabs.map((tab, i) => (
          <button key={i} ref={(el) => { tabRefs.current[i] = el }} type={'button'} role={'tab'}
                  id={`${id}-tab-${i}`} aria-selected={i === active} aria-controls={`${id}-panel`}
                  tabIndex={i === active ? 0 : -1} onClick={() => setActive(i)}
                  className={`-mb-px shrink-0 border-b-2 px-3 py-1.5 text-sm outline-none focus-visible:bg-muted ${
                    i === active ? 'border-primary font-medium' : 'border-transparent text-muted-foreground hover:text-foreground'}`}>
            {tab.label}
          </button>
        ))}
      </div>
      <div role={'tabpanel'} id={`${id}-panel`} aria-labelledby={`${id}-tab-${active}`} className={'min-w-0 p-3'}>
        <ChildContent key={active} item={current} message={message} empty={'Empty tab'} />
      </div>
    </div>
  )
}
