import React from 'react'
import { ChevronRightIcon } from 'lucide-react'
import { WidgetRendererProps } from '@/components/xchat/chat.types.ts'
import { ChildContent, ChildContentData } from './child-content.tsx'

type Section = ChildContentData & { title: string; badge?: string; open?: boolean }

type AccordionData = { sections: Section[]; multiple?: boolean }

/**
 * geenii.accordion — data: { sections: { title, badge?, open?, widget?, text? }[], multiple? = true }
 * Collapsible sections, each holding a nested widget or markdown `text`; `open` sections start expanded.
 * With `multiple: false`, opening a section closes the others. Closed sections are not mounted.
 */
export const AccordionWidget = ({ data, message }: WidgetRendererProps<AccordionData | null>) => {
  const sections = (Array.isArray(data?.sections) ? data.sections : []).filter((s): s is Section => typeof s?.title === 'string')
  const multiple = data?.multiple ?? true
  const [open, setOpen] = React.useState(() => {
    const initial = sections.flatMap((s, i) => (s.open ? [i] : []))
    return new Set(multiple ? initial : initial.slice(0, 1))
  })
  const id = React.useId()

  if (sections.length === 0) return <div className={'text-sm text-muted-foreground'}>No sections</div>

  const toggle = (i: number) => setOpen((prev) => {
    const next = new Set(multiple ? prev : [...prev].filter((j) => j === i))
    if (next.has(i)) next.delete(i)
    else next.add(i)
    return next
  })

  return (
    <div className={'min-w-0 divide-y rounded-md border'}>
      {sections.map((section, i) => {
        const expanded = open.has(i)
        return (
          <div key={i}>
            <button type={'button'} id={`${id}-header-${i}`} aria-expanded={expanded} aria-controls={`${id}-section-${i}`}
                    onClick={() => toggle(i)}
                    className={'flex w-full items-center gap-2 px-3 py-2 text-left text-sm outline-none hover:bg-muted/50 focus-visible:bg-muted'}>
              <ChevronRightIcon className={`size-4 shrink-0 text-muted-foreground transition-transform ${expanded ? 'rotate-90' : ''}`} />
              <span className={`min-w-0 flex-1 truncate ${expanded ? 'font-medium' : ''}`}>{section.title}</span>
              {section.badge && (
                <span className={'shrink-0 rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground'}>{section.badge}</span>
              )}
            </button>
            {expanded && (
              <div role={'region'} id={`${id}-section-${i}`} aria-labelledby={`${id}-header-${i}`} className={'min-w-0 px-3 pb-3 pt-1'}>
                <ChildContent item={section} message={message} />
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
