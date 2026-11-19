import React from 'react'
import { ChevronRightIcon, WrenchIcon, CheckIcon, XIcon, LoaderIcon, HandIcon } from 'lucide-react'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible.tsx'
import { Badge } from '@/components/ui/badge.tsx'
import { Button } from '@/components/ui/button.tsx'
import { useChat, useChatInteractionUi } from '@/components/xchat/chat-context.tsx'
import { useToolCallIndex } from '@/components/xchat/chat-tool-calls.ts'
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

/** A tool approval request: an interaction whose interaction_id is the tool call_id */
export const isToolApproval = (part: UserInteractionContent): boolean => part.interaction_type === 'tool_call_request'

/** The tool name of an approval request, taken from its text ("... call tool 'name' ..."); null if not found. */
export const approvalToolName = (part: UserInteractionContent): string | null =>
  /tool '([^']+)'/.exec(part.text)?.[1] ?? null

const ANSWER_LABELS: Record<string, string> = { allow: 'allowed', deny: 'denied', yes: 'confirmed', no: 'rejected' }

/** Past-tense label of a choice, e.g. "Allow" -> "allowed"; unknown choices are shown as they are. */
export const answerLabel = (choice: string): string => ANSWER_LABELS[choice.toLowerCase()] ?? choice

const AnswerBadge = ({ answer }: { answer: string | null | undefined }) => {
  if (answer == null) return <Badge variant={'secondary'}>no answer</Badge>
  const label = answerLabel(answer)
  const negative = ['denied', 'rejected'].includes(label)
  return <Badge variant={negative ? 'destructive' : 'outline'}>{negative ? <XIcon /> : <CheckIcon />}{label}</Badge>
}

/** Shown while a question is pending; once dismissed from the dialog, it offers to reopen it. */
const AwaitingBadge = ({ id }: { id: string }) => {
  const { dismissed, review } = useChatInteractionUi()
  return (
    <span className={'flex items-center gap-2'}>
      <Badge variant={'secondary'}><HandIcon className={'text-amber-600'} />awaiting approval</Badge>
      {dismissed.has(id) && <Button size={'sm'} variant={'outline'} className={'h-6 px-2 text-xs'}
                                    onClick={() => review(id)}>Review</Button>}
    </span>
  )
}

/** One compact line in the chat; the question itself is asked in the ChatInteractionDialog. */
const InteractionRow = (props: { icon: React.ReactNode; children: React.ReactNode; badge: React.ReactNode }) => (
  <div className={'flex min-w-0 items-center gap-2 text-sm text-muted-foreground'}>
    <span className={'shrink-0 [&_svg]:size-4'}>{props.icon}</span>
    <span className={'min-w-0 truncate'}>{props.children}</span>
    <span className={'shrink-0'}>{props.badge}</span>
  </div>
)

/**
 * A question for the user (e.g. tool approval), shown as one status line: the choices are made in the
 * ChatInteractionDialog while the backend waits; afterwards the line shows the answer.
 */
export const InteractionPart = ({ part }: ContentPartRendererProps<UserInteractionContent>) => {
  const pending = useChat((s) => Boolean(s.pendingInteractions[part.interaction_id]))
  const { results, calls } = useToolCallIndex()

  if (isToolApproval(part)) {
    const result = results.get(part.interaction_id)
    const name = calls.get(part.interaction_id)?.name ?? approvalToolName(part) ?? result?.name ?? 'tool'
    // history may lack the choice; then the tool result tells whether the call ran
    const answer = part.choice ?? (result ? (/rejected/i.test(toolResultError(result) ?? '') ? 'Deny' : 'Allow') : null)
    return (
      <InteractionRow icon={<WrenchIcon />} badge={pending ? <AwaitingBadge id={part.interaction_id} /> : <AnswerBadge answer={answer} />}>
        Calling tool <span className={'font-mono text-foreground'}>{name}</span> …
      </InteractionRow>
    )
  }

  return (
    <InteractionRow icon={<HandIcon />} badge={pending ? <AwaitingBadge id={part.interaction_id} /> : <AnswerBadge answer={part.choice} />}>
      {part.text}
    </InteractionRow>
  )
}

/** A yes/no confirmation, shown as one status line; it is answered in the ChatInteractionDialog. */
export const ConfirmationPart = ({ part }: ContentPartRendererProps<UserConfirmationContent>) => {
  const pending = useChat((s) => Boolean(s.pendingInteractions[part.confirmation_id]))
  const answer = part.confirmed == null ? null : part.confirmed ? 'yes' : 'no'
  return (
    <InteractionRow icon={<HandIcon />} badge={pending ? <AwaitingBadge id={part.confirmation_id} /> : <AnswerBadge answer={answer} />}>
      {part.text}
    </InteractionRow>
  )
}
