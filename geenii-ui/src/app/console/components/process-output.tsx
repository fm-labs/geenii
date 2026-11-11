import * as React from 'react'
import { RefreshCwIcon } from 'lucide-react'
import { Button } from '@/components/ui/button.tsx'
import { Label } from '@/components/ui/label.tsx'
import { Switch } from '@/components/ui/switch.tsx'
import { useApi } from '@/context/api-context.tsx'
import { ApiError, readProblem } from '@/api/api-error.ts'
import { cn } from 'cn'

/** Bytes per output request */
const CHUNK = 64 * 1024

type Stream = 'stdout' | 'stderr'

/**
 * Captured output of a process, read in CHUNK-byte pages via offset/limit.
 *
 * A page is kept once the page after it exists; the last, still growing page is
 * re-read on every pull and replaced. The server returns a UTF-8 character split
 * across pages whole with the page holding its first byte, so pages concatenate cleanly.
 */
const ProcessOutput = ({ pid, active, tick }: {
  pid: string
  /** The process is pending or running: keep pulling while following */
  active: boolean
  /** Changes on every poll of the parent view */
  tick: number
}) => {
  const { fetch } = useApi()
  const [stream, setStream] = React.useState<Stream>('stdout')
  const [follow, setFollow] = React.useState(true)
  const [committed, setCommitted] = React.useState('')
  const [pending, setPending] = React.useState('')
  const [status, setStatus] = React.useState<string>('')
  const [error, setError] = React.useState<string | null>(null)
  const preRef = React.useRef<HTMLPreElement>(null)
  // Pull state outside React, so overlapping pulls and resets can be detected
  const st = React.useRef({ offset: 0, gen: 0, busy: false, again: false })

  const getChunk = React.useCallback(async (offset: number) => {
    const q = new URLSearchParams({ stream, offset: String(offset), limit: String(CHUNK) })
    const res = await fetch(`/api/v1/pm/processes/${encodeURIComponent(pid)}/output?${q}`)
    if (!res.ok) throw new ApiError(res.status, await readProblem(res))
    return await res.text()
  }, [fetch, pid, stream])

  const pull = React.useCallback(async () => {
    const s = st.current
    // A pull requested mid-pull (e.g. the last one after the process exited) runs right after it
    if (s.busy) {
      s.again = true
      return
    }
    const gen = s.gen
    s.busy = true
    s.again = false
    const pre = preRef.current
    const atBottom = !pre || pre.scrollTop + pre.clientHeight >= pre.scrollHeight - 4
    try {
      let added = ''
      let chunk = await getChunk(s.offset)
      let last = ''
      while (chunk) {
        const next = await getChunk(s.offset + CHUNK)
        if (gen !== s.gen) return
        if (!next) {
          last = chunk
          break
        }
        added += chunk
        s.offset += CHUNK
        chunk = next
      }
      if (gen !== s.gen) return
      if (added) setCommitted((c) => c + added)
      setPending(last)
      setError(null)
      setStatus('')
      if (atBottom && follow) {
        requestAnimationFrame(() => {
          if (preRef.current) preRef.current.scrollTop = preRef.current.scrollHeight
        })
      }
    } catch (err) {
      if (gen !== s.gen) return
      if (err instanceof ApiError && err.status === 404) setStatus('no log')
      else setError(err?.message || 'Unknown error')
    } finally {
      if (gen === s.gen) {
        s.busy = false
        if (s.again) pull()
      }
    }
  }, [getChunk, follow])

  const reset = React.useCallback(() => {
    const s = st.current
    s.gen++
    s.offset = 0
    s.busy = s.again = false
    setCommitted('')
    setPending('')
    setStatus('')
    setError(null)
  }, [])

  // Start over for another process or stream
  React.useEffect(() => {
    reset()
  }, [pid, stream, reset])

  // Pull once after a reset, then on polls while the process runs, plus once more after it finished
  const wasActive = React.useRef(active)
  React.useEffect(() => {
    pull()
    // pull is recreated with getChunk, i.e. after a reset
  }, [pull])
  React.useEffect(() => {
    if (follow && (active || wasActive.current)) pull()
    wasActive.current = active
    // only on polls
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tick])

  const size = committed.length + pending.length

  return (
    <div className="flex min-h-0 flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <div className="inline-flex rounded-md border p-0.5">
          {(['stdout', 'stderr'] as Stream[]).map((s) => (
            <button key={s} onClick={() => setStream(s)}
                    className={cn('rounded px-2.5 py-1 font-mono text-xs',
                      stream === s ? 'bg-secondary text-secondary-foreground' : 'text-muted-foreground hover:text-foreground')}>
              {s}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <Switch id="pm-follow" size="sm" checked={follow} onCheckedChange={setFollow} />
          <Label htmlFor="pm-follow" className="text-xs font-normal">Follow</Label>
        </div>
        <span className="ml-auto text-xs text-muted-foreground">
          {status || (size ? `${size.toLocaleString()} chars` : 'no output')}
        </span>
        <Button size="sm" variant="ghost" onClick={() => { reset(); setTimeout(pull) }} title="Reload output">
          <RefreshCwIcon />
        </Button>
      </div>
      {error && <div className="text-xs text-destructive">{error}</div>}
      <pre ref={preRef}
           className="h-96 overflow-auto whitespace-pre-wrap break-all rounded-md border bg-muted/40 p-3 font-mono text-xs leading-relaxed">
        {committed}{pending}
      </pre>
    </div>
  )
}

export default ProcessOutput
