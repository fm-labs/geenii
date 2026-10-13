import React from 'react'
import { ChevronRightIcon, WrenchIcon, CheckIcon, XIcon, LoaderIcon, HandIcon } from 'lucide-react'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible.tsx'
import { Badge } from '@/components/ui/badge.tsx'
import { Button } from '@/components/ui/button.tsx'
import { useChat, useChatActions } from '@/components/xchat/chat-context.tsx'
import {
  ContentPartRendererProps,
  FunctionCallContent,
  ToolCallContent,
  ToolCallResultContent,
  UserConfirmationContent,
  UserInteractionContent,
} from '@/components/xchat/chat.types.ts'
import { JsonBlock } from '@/components/xchat/parts/media-parts.tsx'

type ToolState = 'pending' | 'done' | 'failed'

/** A tool result is a failure if it carries an error, or the agent's {"error": ...} convention. */
export const toolResultError = (result?: ToolCallResultContent): string | null => {
  if (!result) return null
  if (result.error) return result.error
  const value = result.result as any
  return value && typeof value === 'object' && !Array.isArray(value) && typeof value.error === 'string'
    ? value.error
    : null
}

const StateBadge = ({ state }: { state: ToolState }) => {
  if (state === 'pending') return <Badge variant={'secondary'}><LoaderIcon className={'animate-spin'} />running</Badge>
  if (state === 'failed') return <Badge variant={'destructive'}><XIcon />failed</Badge>
  return <Badge variant={'outline'}><CheckIcon />done</Badge>
}

const ToolCard = (props: {
  name: string
  args?: Record<string, unknown> | null
  state: ToolState
  result?: unknown
  error?: string | null
}) => {
  const [open, setOpen] = React.useState(false)
  const hasArgs = props.args && Object.keys(props.args).length > 0
  return (
    <Collapsible open={open} onOpenChange={setOpen} className={'rounded-md border text-sm'}>
      <CollapsibleTrigger className={'flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-accent/50'}>
        <ChevronRightIcon className={`size-4 shrink-0 transition-transform ${open ? 'rotate-90' : ''}`} />
        <WrenchIcon className={'size-4 shrink-0 text-muted-foreground'} />
        <span className={'font-mono truncate'}>{props.name}</span>
        <span className={'ml-auto'}><StateBadge state={props.state} /></span>
      </CollapsibleTrigger>
      <CollapsibleContent className={'space-y-2 border-t px-3 py-2'}>
        {hasArgs && <div>
          <div className={'text-xs font-medium text-muted-foreground mb-1'}>Arguments</div>
          <JsonBlock data={props.args} />
        </div>}
        {props.error && <div className={'text-destructive'}>{props.error}</div>}
        {props.state !== 'pending' && props.result !== undefined && !props.error && <div>
          <div className={'text-xs font-medium text-muted-foreground mb-1'}>Result</div>
          <JsonBlock data={props.result} />
        </div>}
      </CollapsibleContent>
    </Collapsible>
  )
}

/** A tool call request; shows its result once the matching tool_call_result (same call_id) has arrived. */
export const ToolCallPart = ({ part, result }: ContentPartRendererProps<ToolCallContent>) => {
  const error = toolResultError(result)
  return <ToolCard name={part.name} args={part.arguments}
                   state={!result ? 'pending' : error ? 'failed' : 'done'}
                   result={result?.result} error={error} />
}

/** A tool result without a rendered tool call (the agent often sends only the result). */
export const ToolCallResultPart = ({ part }: ContentPartRendererProps<ToolCallResultContent>) => {
  const error = toolResultError(part)
  return <ToolCard name={part.name} args={part.arguments} state={error ? 'failed' : 'done'}
                   result={part.result} error={error} />
}

export const FunctionCallPart = ({ part }: ContentPartRendererProps<FunctionCallContent>) => (
  <ToolCard name={part.name} args={part.arguments} state={part.result == null ? 'pending' : 'done'}
            result={part.result ?? undefined} />
)

const InteractionBox = (props: { text: string; children: React.ReactNode }) => (
  <div className={'rounded-md border border-amber-500/50 bg-amber-500/5 p-3 text-sm space-y-2'}>
    <div className={'flex gap-2'}>
      <HandIcon className={'size-4 shrink-0 mt-0.5 text-amber-600'} />
      <div className={'whitespace-pre-wrap break-words'}>{props.text}</div>
    </div>
    <div className={'flex flex-wrap items-center gap-2 pl-6'}>{props.children}</div>
  </div>
)

/** A question for the user (e.g. tool approval). Choices are only clickable while the backend waits for them. */
export const InteractionPart = ({ part }: ContentPartRendererProps<UserInteractionContent>) => {
  const { respond } = useChatActions()
  const pending = useChat((s) => Boolean(s.pendingInteractions[part.interaction_id]))
  const [sending, setSending] = React.useState(false)

  const choose = (choice: string) => {
    setSending(true)
    respond({ interactionId: part.interaction_id, choice }).catch(() => setSending(false))
  }

  return (
    <InteractionBox text={part.text}>
      {pending
        ? part.choices.map((choice, i) => (
          <Button key={choice} size={'sm'} variant={i === 0 ? 'default' : 'outline'} disabled={sending}
                  onClick={() => choose(choice)}>{choice}</Button>
        ))
        : <Badge variant={'secondary'}>{part.choice ?? 'No answer'}</Badge>}
    </InteractionBox>
  )
}

/** A yes/no confirmation, answered through respond() with the confirmation_id. */
export const ConfirmationPart = ({ part }: ContentPartRendererProps<UserConfirmationContent>) => {
  const { respond } = useChatActions()
  const pending = useChat((s) => Boolean(s.pendingInteractions[part.confirmation_id]))
  const answer = part.confirmed == null ? null : part.confirmed ? 'Confirmed' : 'Rejected'

  return (
    <InteractionBox text={part.text}>
      {pending
        ? <>
          <Button size={'sm'} onClick={() => respond({ interactionId: part.confirmation_id, choice: 'yes' })}>Confirm</Button>
          <Button size={'sm'} variant={'outline'}
                  onClick={() => respond({ interactionId: part.confirmation_id, choice: 'no' })}>Reject</Button>
        </>
        : <Badge variant={'secondary'}>{answer ?? 'No answer'}</Badge>}
    </InteractionBox>
  )
}
