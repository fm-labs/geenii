import React from 'react'
import { cn } from 'cn'
import { getServiceLog, SERVICE_LABELS, ServiceName } from './desktop-runtime.ts'

const POLL_MS = 2000
const LINES = 300
// eslint-disable-next-line no-control-regex
const ANSI = /\x1b\[[0-9;?]*[A-Za-z]/g
const SERVICES: ServiceName[] = ['server', 'daemon']

/** Live tail of a service log, polled while mounted. Sticks to the bottom unless scrolled up. */
const ServiceLogView = () => {
  const [service, setService] = React.useState<ServiceName>('server')
  const [log, setLog] = React.useState<string | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const ref = React.useRef<HTMLPreElement>(null)
  const stickToBottom = React.useRef(true)

  React.useEffect(() => {
    let cancelled = false
    let timer: ReturnType<typeof setTimeout>
    setLog(null)
    setError(null)
    stickToBottom.current = true
    const poll = async () => {
      try {
        const text = await getServiceLog(service, LINES)
        if (!cancelled) {
          setLog(text.replace(ANSI, ''))
          setError(null)
        }
      } catch (e) {
        if (!cancelled) setError(String(e))
      }
      if (!cancelled) timer = setTimeout(poll, POLL_MS)
    }
    poll()
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [service])

  React.useLayoutEffect(() => {
    const el = ref.current
    if (el && stickToBottom.current) el.scrollTop = el.scrollHeight
  }, [log])

  const onScroll = () => {
    const el = ref.current
    if (el) stickToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 24
  }

  return (
    <section className="min-w-0">
      <div className="mb-2 flex items-center gap-3">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Logs <span className="font-normal normal-case tracking-normal">(last {LINES} lines)</span>
        </h3>
        <div className="inline-flex rounded-md border bg-background p-0.5 text-xs" role="tablist">
          {SERVICES.map((s) => (
            <button
              key={s}
              type="button"
              role="tab"
              aria-selected={s === service}
              onClick={() => setService(s)}
              className={cn(
                'rounded px-2 py-0.5',
                s === service ? 'bg-accent font-medium text-foreground' : 'text-muted-foreground hover:text-foreground',
              )}
            >
              {SERVICE_LABELS[s]}
            </button>
          ))}
        </div>
      </div>
      {error && <div className="mb-2 text-xs text-destructive">{error}</div>}
      <pre
        ref={ref}
        onScroll={onScroll}
        className="h-64 overflow-auto rounded-md border bg-background p-3 font-mono text-xs leading-5 whitespace-pre"
      >
        {log === null ? 'Loading…' : log || 'The log is empty.'}
      </pre>
    </section>
  )
}

export default ServiceLogView
