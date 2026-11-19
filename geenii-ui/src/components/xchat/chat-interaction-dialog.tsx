import React from 'react'
import { HandIcon, WrenchIcon } from 'lucide-react'
import { Button } from '@/components/ui/button.tsx'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog.tsx'
import { useChat, useChatActions, useChatInteractionUi } from '@/components/xchat/chat-context.tsx'
import { PendingInteraction, ToolCallContent } from '@/components/xchat/chat.types.ts'
import { buildToolCallIndex } from '@/components/xchat/chat-tool-calls.ts'
import { JsonBlock } from '@/components/xchat/parts/media-parts.tsx'
import { approvalToolName, isToolApproval } from '@/components/xchat/parts/tool-parts.tsx'

type Question = {
  id: string
  icon: React.ReactNode
  title: string
  description: React.ReactNode
  text: string
  /** For tool approvals: the tool call the request belongs to (same call_id), if it was sent */
  toolCall?: ToolCallContent
  /** [label, choice sent to the backend]; the first one is the primary action */
  choices: [string, string][]
}

const toQuestion = (p: PendingInteraction, toolCalls: Map<string, ToolCallContent>): Question => {
  if (p.type === 'confirmation') {
    return {
      id: p.confirmation_id,
      icon: <HandIcon className={'size-5 text-amber-600'} />,
      title: 'Confirmation required',
      description: 'The agent waits for your confirmation.',
      text: p.text,
      choices: [['Confirm', 'yes'], ['Reject', 'no']],
    }
  }
  if (isToolApproval(p)) {
    const toolCall = toolCalls.get(p.interaction_id)
    const name = toolCall?.name ?? approvalToolName(p)
    return {
      id: p.interaction_id,
      icon: <WrenchIcon className={'size-5 text-amber-600'} />,
      title: 'Allow tool call?',
      description: name
        ? <>The agent wants to call the tool <span className={'font-mono text-foreground'}>{name}</span>.</>
        : 'The agent wants to call a tool.',
      text: p.text,
      toolCall,
      choices: p.choices.map((c) => [c, c]),
    }
  }
  return {
    id: p.interaction_id,
    icon: <HandIcon className={'size-5 text-amber-600'} />,
    title: 'Input required',
    description: 'The agent waits for your answer.',
    text: p.text,
    choices: p.choices.map((c) => [c, c]),
  }
}

/**
 * Asks the user the oldest pending interaction (tool approvals, confirmations, choices) in a modal popup.
 * Closes once answered; the chat then shows the answer as a status line. "Stop" cancels the turn instead.
 * Esc dismisses a question without answering; it stays pending and can be reopened from its line in the chat.
 * Must be used within a ChatProvider; <Chat> includes it.
 */
const ChatInteractionDialog = () => {
  const pending = useChat((s) => s.pendingInteractions)
  const messages = useChat((s) => s.messages)
  const toolCalls = React.useMemo(() => buildToolCallIndex(messages).calls, [messages])
  const { respond, cancel } = useChatActions()
  const { dismissed, dismiss } = useChatInteractionUi()
  const [sending, setSending] = React.useState<string | null>(null)

  const current = React.useMemo(() => {
    const first = Object.entries(pending).find(([id]) => !dismissed.has(id))?.[1]
    return first ? toQuestion(first, toolCalls) : null
  }, [pending, dismissed, toolCalls])

  // keep the last question while the dialog animates out
  const [shown, setShown] = React.useState<Question | null>(current)
  React.useEffect(() => {
    if (current) setShown(current)
  }, [current])

  const choose = (choice: string) => {
    if (!current) return
    setSending(current.id)
    respond({ interactionId: current.id, choice }).catch(() => undefined).finally(() => setSending(null))
  }

  const q = current ?? shown
  const busy = sending !== null && sending === current?.id

  return (
    <Dialog open={current !== null}>
      <DialogContent showCloseButton={false}
                     onEscapeKeyDown={() => current && dismiss(current.id)}
                     onInteractOutside={(e) => e.preventDefault()}>
        {q && <>
          <DialogHeader>
            <DialogTitle className={'flex items-center gap-2'}>{q.icon}{q.title}</DialogTitle>
            <DialogDescription>{q.description}</DialogDescription>
          </DialogHeader>
          {q.toolCall
            ? <div className={'min-w-0 space-y-1'}>
              <div className={'text-xs font-medium text-muted-foreground'}>Arguments</div>
              <JsonBlock data={q.toolCall.arguments ?? {}} />
              {q.toolCall.call_id && <div className={'text-xs text-muted-foreground'}>
                Call ID <span className={'font-mono'}>{q.toolCall.call_id}</span>
              </div>}
            </div>
            : q.text && <div className={'max-h-64 overflow-auto rounded-md border bg-muted/30 p-3 text-sm whitespace-pre-wrap break-words'}>
              {q.text}
            </div>}
          <DialogFooter className={'sm:justify-between'}>
            <Button variant={'ghost'} disabled={busy} onClick={cancel}>Stop</Button>
            <div className={'flex flex-col-reverse gap-2 sm:flex-row'}>
              {[...q.choices].reverse().map(([label, choice], i, all) => (
                <Button key={choice} disabled={busy} autoFocus={i === all.length - 1}
                        variant={i === all.length - 1 ? 'default' : 'outline'}
                        onClick={() => choose(choice)}>{label}</Button>
              ))}
            </div>
          </DialogFooter>
        </>}
      </DialogContent>
    </Dialog>
  )
}

export default ChatInteractionDialog
