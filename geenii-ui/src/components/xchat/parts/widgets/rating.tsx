import React from 'react'
import { SendIcon, StarIcon, ThumbsDownIcon, ThumbsUpIcon } from 'lucide-react'
import { Button } from '@/components/ui/button.tsx'
import { Textarea } from '@/components/ui/textarea.tsx'
import { WidgetRendererProps } from '@/components/xchat/chat.types.ts'
import { messageText, useChatReply } from './use-chat-reply.ts'

type RatingData = { type?: 'stars' | 'thumbs'; max?: number; comment?: boolean; once?: boolean }

/** The rating as the user message, e.g. "Rating: ★★★★☆ (4/5)" or "Rating: 👍 helpful", plus the comment */
export const ratingMessage = (type: 'stars' | 'thumbs', value: number, max: number, comment: string) => {
  const rating = type === 'thumbs'
    ? (value > 0 ? '👍 helpful' : '👎 not helpful')
    : `${'★'.repeat(value)}${'☆'.repeat(max - value)} (${value}/${max})`
  return comment.trim() ? `Rating: ${rating}\nComment: ${comment.trim()}` : `Rating: ${rating}`
}

/** The value of a sent rating message (for the answered state after reloading), or null */
const parseRating = (text: string, type: 'stars' | 'thumbs'): number | null => {
  if (type === 'thumbs') return text.startsWith('Rating: 👍') ? 1 : text.startsWith('Rating: 👎') ? -1 : null
  const match = /^Rating: .*\((\d+)\/\d+\)/.exec(text)
  return match ? Number(match[1]) : null
}

/**
 * geenii.rating — data: { type? = 'stars' | 'thumbs', max? = 5 (stars, 3–10), comment? = false, once? = true }
 * Sends the rating (and with `comment`, an optional comment) as a user message.
 */
export const RatingWidget = ({ data, message }: WidgetRendererProps<RatingData | null>) => {
  const type = data?.type === 'thumbs' ? 'thumbs' : 'stars'
  const max = Math.min(10, Math.max(3, Math.round(data?.max ?? 5)))
  const { reply, busy, answer, error } = useChatReply(message)
  const [value, setValue] = React.useState<number | null>(null)
  const [hover, setHover] = React.useState<number | null>(null)
  const [comment, setComment] = React.useState('')
  const [sent, setSent] = React.useState(false)

  const answered = answer ? parseRating(messageText(answer), type) : null
  const locked = (data?.once ?? true) && (sent || answer != null)
  const shown = locked ? (answered ?? value) : (hover ?? value)

  const send = async (v: number) => {
    if (await reply(ratingMessage(type, v, max, comment))) setSent(true)
  }
  // without a comment field a click sends right away; with one, it selects and "Send" sends
  const pick = (v: number) => {
    setValue(v)
    if (!data?.comment) void send(v)
  }

  return (
    <div className={'inline-flex max-w-md flex-col items-start gap-2'}>
      <div className={'flex items-center gap-1'} onMouseLeave={() => setHover(null)}>
        {type === 'thumbs' ? (
          <>
            <Button size={'icon'} variant={shown === 1 ? 'default' : 'outline'} disabled={busy || locked}
                    aria-label={'Helpful'} aria-pressed={shown === 1} onClick={() => pick(1)}><ThumbsUpIcon /></Button>
            <Button size={'icon'} variant={shown === -1 ? 'default' : 'outline'} disabled={busy || locked}
                    aria-label={'Not helpful'} aria-pressed={shown === -1} onClick={() => pick(-1)}><ThumbsDownIcon /></Button>
          </>
        ) : Array.from({ length: max }, (_, i) => i + 1).map((n) => (
          <button key={n} type={'button'} disabled={busy || locked} aria-label={`${n} of ${max}`} aria-pressed={value === n}
                  onMouseEnter={() => setHover(n)} onFocus={() => setHover(n)} onBlur={() => setHover(null)} onClick={() => pick(n)}
                  className={'rounded p-0.5 outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-default'}>
            <StarIcon className={`size-6 ${shown != null && n <= shown ? 'fill-amber-400 text-amber-400' : 'text-muted-foreground'}`} />
          </button>
        ))}
        {locked && <span className={'ml-2 text-xs text-muted-foreground'}>Thanks!</span>}
      </div>
      {data?.comment && !locked && (
        <div className={'flex w-full flex-col items-start gap-2'}>
          <Textarea value={comment} onChange={(e) => setComment(e.target.value)} placeholder={'Comment (optional)'}
                    disabled={busy} className={'min-h-16 text-sm'} />
          <Button size={'sm'} disabled={busy || value == null} onClick={() => value != null && send(value)}>
            <SendIcon />Send
          </Button>
        </div>
      )}
      {error && <span className={'text-xs text-destructive'}>{error}</span>}
    </div>
  )
}
