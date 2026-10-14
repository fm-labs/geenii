import { CheckIcon } from 'lucide-react'
import { Button } from '@/components/ui/button.tsx'
import { WidgetRendererProps } from '@/components/xchat/chat.types.ts'
import { messageText, useChatReply } from './use-chat-reply.ts'

type Option = string | { label: string; message?: string }

const optionMessage = (option: Option) => (typeof option === 'string' ? option : option.message || option.label)

/**
 * geenii.choices — data: { options: (string | { label, message? })[], once? = true }
 * Suggested replies: a click sends the option's message (or label) as a user message.
 * With `once`, the buttons lock as soon as the conversation has moved on (any later user message).
 */
export const ChoicesWidget = ({ data, message }: WidgetRendererProps<{ options: Option[]; once?: boolean } | null>) => {
  const options = (Array.isArray(data?.options) ? data.options : [])
    .filter((o): o is Option => typeof o === 'string' || (o != null && typeof o.label === 'string'))
  const { reply, busy, answer, error } = useChatReply(message)
  const once = data?.once ?? true
  const answerText = answer ? messageText(answer) : null
  const locked = once && answer != null

  return (
    <div className={'flex flex-col items-start gap-1'}>
      <div className={'flex flex-wrap gap-2'}>
        {options.map((option, i) => {
          const chosen = answerText != null && answerText === optionMessage(option)
          return (
            <Button key={i} size={'sm'} variant={chosen ? 'default' : 'outline'} disabled={busy || locked}
                    onClick={() => reply(optionMessage(option))}>
              {chosen && <CheckIcon />}
              {typeof option === 'string' ? option : option.label}
            </Button>
          )
        })}
      </div>
      {error && <span className={'text-xs text-destructive'}>{error}</span>}
    </div>
  )
}
