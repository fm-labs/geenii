import React from 'react'
import { getServerLog } from './desktop-runtime.ts'

const POLL_MS = 2000
const LINES = 300
// eslint-disable-next-line no-control-regex
const ANSI = /\x1b\[[0-9;?]*[A-Za-z]/g

/** Live tail of the server log, polled while mounted. Sticks to the bottom unless scrolled up. */
const ServerLogView = () => {
  const [log, setLog] = React.useState<string | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const ref = React.useRef<HTMLPreElement>(null)
  const stickToBottom = React.useRef(true)

  React.useEffect(() => {
    let cancelled = false
    let timer: ReturnType<typeof setTimeout>
    const poll = async () => {
      try {
        const text = await getServerLog(LINES)
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
  }, [])

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
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Server log <span className="font-normal normal-case tracking-normal">(last {LINES} lines)</span>
      </h3>
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

export default ServerLogView
