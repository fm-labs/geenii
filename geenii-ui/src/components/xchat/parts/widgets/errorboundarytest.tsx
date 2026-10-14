import React from 'react'
import { WidgetRendererProps } from '@/components/xchat/chat.types.ts'

/**
 * geenii.dev.errorboundarytest — data: { message? = 'Widget crashed on purpose', delay? = 0 }
 * Development aid: throws while rendering, to see the widget error boundary at work.
 * With `delay` (ms), it first renders a countdown and crashes after that, i.e. from a later re-render.
 */
export const ErrorBoundaryTestWidget = ({ data }: WidgetRendererProps<{ message?: string; delay?: number } | null>) => {
  const delay = Math.max(0, data?.delay ?? 0)
  const [crash, setCrash] = React.useState(delay === 0)

  React.useEffect(() => {
    if (crash) return
    const timer = setTimeout(() => setCrash(true), delay)
    return () => clearTimeout(timer)
  }, [crash, delay])

  if (crash) throw new Error(data?.message || 'Widget crashed on purpose')
  return <div className={'text-sm text-muted-foreground'}>This widget will crash in {(delay / 1000).toFixed(1)} s…</div>
}
