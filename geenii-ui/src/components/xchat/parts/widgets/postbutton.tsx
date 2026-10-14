import React from 'react'
import { CheckIcon, LoaderIcon, SendIcon, XIcon } from 'lucide-react'
import { Button } from '@/components/ui/button.tsx'
import { WidgetRendererProps } from '@/components/xchat/chat.types.ts'
import { safeUrl } from './safe-url.ts'

type PostButtonData = {
  url: string
  payload?: unknown
  label?: string
  /** expected response status (default 200); anything else counts as failed */
  expect?: number
  /** ask for confirmation with this question before sending */
  confirm?: string
  /** allow sending again after a success (default: the button stays done) */
  repeat?: boolean
  headers?: Record<string, string>
}

type State =
  | { status: 'idle' | 'confirming' | 'sending' | 'done' }
  | { status: 'failed'; error: string }

const TIMEOUT_MS = 15_000

/**
 * geenii.postbutton — data: { url, payload?, label? = 'Send', expect? = 200, confirm?, repeat? = false, headers? }
 * On click it POSTs the payload as JSON (without cookies) and succeeds only on the expected status.
 */
export const PostButtonWidget = ({ data }: WidgetRendererProps<PostButtonData | null>) => {
  const url = safeUrl(data?.url)
  const expect = data?.expect ?? 200
  const [state, setState] = React.useState<State>({ status: 'idle' })
  const abortRef = React.useRef<AbortController | null>(null)

  // a request still running when the widget goes away is cancelled
  React.useEffect(() => () => abortRef.current?.abort(), [])

  if (!url) return <div className={'text-sm text-muted-foreground italic'}>[postbutton: invalid url {data?.url}]</div>

  const send = async () => {
    const controller = new AbortController()
    abortRef.current = controller
    const timer = setTimeout(() => controller.abort(), TIMEOUT_MS)
    setState({ status: 'sending' })
    try {
      const res = await fetch(url.href, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...data?.headers },
        body: JSON.stringify(data?.payload ?? {}),
        credentials: 'omit',
        signal: controller.signal,
      })
      setState(res.status === expect
        ? { status: 'done' }
        : { status: 'failed', error: `${res.status}${res.statusText ? ` ${res.statusText}` : ''} (expected ${expect})` })
    } catch (err) {
      if (abortRef.current !== controller) return
      const timedOut = controller.signal.aborted
      setState({ status: 'failed', error: timedOut ? 'Timed out' : 'Network error (unreachable or blocked by CORS)' })
      if (!timedOut) console.warn('postbutton request failed', err)
    } finally {
      clearTimeout(timer)
    }
  }

  const label = data?.label || 'Send'
  const { status } = state
  const locked = status === 'sending' || (status === 'done' && !data?.repeat)

  return (
    <div className={'inline-flex flex-col items-start gap-1'}>
      {status === 'confirming' ? (
        <div className={'flex flex-wrap items-center gap-2 text-sm'}>
          <span>{data?.confirm}</span>
          <Button size={'sm'} onClick={send}>Yes</Button>
          <Button size={'sm'} variant={'outline'} onClick={() => setState({ status: 'idle' })}>Cancel</Button>
        </div>
      ) : (
        <Button
          size={'sm'}
          variant={status === 'done' ? 'outline' : status === 'failed' ? 'destructive' : 'default'}
          disabled={locked}
          onClick={() => (data?.confirm ? setState({ status: 'confirming' }) : send())}
        >
          {status === 'sending' ? <LoaderIcon className={'animate-spin'} />
            : status === 'done' ? <CheckIcon />
              : status === 'failed' ? <XIcon /> : <SendIcon />}
          {status === 'sending' ? 'Sending…' : status === 'done' ? 'Sent' : status === 'failed' ? `Retry: ${label}` : label}
        </Button>
      )}
      <span className={'text-xs text-muted-foreground'}>
        {state.status === 'failed'
          ? <span className={'text-destructive'}>Failed: {state.error}</span>
          : <>POST {url.host}{url.pathname}</>}
      </span>
    </div>
  )
}
