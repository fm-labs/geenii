import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip.tsx'
import { Usage } from '@/components/xchat/chat.types.ts'

const compact = new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 })

/** 574 -> "574", 18249 -> "18.2K", 999999 -> "1M" */
export const formatTokens = (n: number) => compact.format(n)

const formatMs = (ms: number) => (ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`)

/**
 * Token usage of the model call that produced a message: the total, with the breakdown in a tooltip.
 * `input_tokens` counts all input; the cache numbers are parts of it.
 */
const ChatMessageUsage = ({ usage }: { usage: Usage }) => {
  const cacheRead = usage.cache_read_input_tokens ?? 0
  const cacheWrite = usage.cache_creation_input_tokens ?? 0
  const rows: [string, string][] = [
    ['Input', usage.input_tokens.toLocaleString()],
    ...(cacheRead ? [['  read from cache', cacheRead.toLocaleString()] as [string, string]] : []),
    ...(cacheWrite ? [['  written to cache', cacheWrite.toLocaleString()] as [string, string]] : []),
    ['Output', usage.output_tokens.toLocaleString()],
    ['Total', usage.total_tokens.toLocaleString()],
    ...(usage.total_duration != null ? [['Time', formatMs(usage.total_duration)] as [string, string]] : []),
  ]

  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span tabIndex={0} className={'cursor-default tabular-nums outline-none focus-visible:underline'}
                aria-label={`${usage.total_tokens} tokens`}>
            {formatTokens(usage.total_tokens)} tokens
          </span>
        </TooltipTrigger>
        <TooltipContent side={'bottom'}>
          <dl className={'grid grid-cols-[auto_auto] gap-x-4 gap-y-0.5'}>
            {rows.map(([label, value]) => (
              <div key={label} className={'contents'}>
                <dt className={label.startsWith(' ') ? 'pl-3 opacity-70' : ''}>{label.trim()}</dt>
                <dd className={'text-right tabular-nums'}>{value}</dd>
              </div>
            ))}
          </dl>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}

export default ChatMessageUsage
