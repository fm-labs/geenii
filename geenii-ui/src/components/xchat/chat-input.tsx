import React from 'react'
import { SendHorizonalIcon, SquareIcon } from 'lucide-react'
import { cn } from 'cn'
import { Button } from '@/components/ui/button.tsx'
import { useChat, useChatActions } from '@/components/xchat/chat-context.tsx'

/** Return true if the key was handled; the input then skips its own handling (e.g. Enter = submit). */
export type ChatInputKeyHandler = (e: React.KeyboardEvent<HTMLTextAreaElement>) => boolean

type ChatInputContextType = {
  draft: string
  setDraft: (draft: string) => void
  submit: () => void
  focus: () => void
  /** Register a key handler that runs before the input's own; returns the unregister function */
  addKeyDownHandler: (handler: ChatInputKeyHandler) => () => void
  disabled: boolean
}

/**
 * Lets input add-ons (voice input, command menu, …) placed inside <ChatInput> read and change the draft.
 * Add-ons can position popups relative to the input box (it is `relative`).
 */
export const ChatInputContext = React.createContext<ChatInputContextType | null>(null)

export const useChatInput = (): ChatInputContextType => {
  const ctx = React.useContext(ChatInputContext)
  if (!ctx) throw new Error('useChatInput must be used within a ChatInput')
  return ctx
}

type ChatInputProps = {
  placeholder?: string
  /** Enter submits, Shift+Enter adds a new line (default true) */
  submitOnEnter?: boolean
  /** Add-ons rendered in the input toolbar, e.g. <ChatVoiceInput /> */
  children?: React.ReactNode
  className?: string
}

/**
 * Textarea that sends to the chat session. While a turn runs the user can keep typing,
 * and the send button becomes a stop button.
 */
const ChatInput = (props: ChatInputProps) => {
  const { placeholder = 'What\'s up?', submitOnEnter = true, children, className } = props
  const { send, cancel } = useChatActions()
  const busy = useChat((s) => s.status === 'submitting' || s.status === 'streaming' || s.status === 'awaiting_input')
  const [draft, setDraft] = React.useState('')
  const textareaRef = React.useRef<HTMLTextAreaElement>(null)
  const keyHandlers = React.useRef(new Set<ChatInputKeyHandler>())

  // grow with the content
  React.useLayoutEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 240)}px`
  }, [draft])

  const submit = React.useCallback(() => {
    if (busy || !draft.trim()) return
    const input = draft
    setDraft('')
    // a failed send restores the draft; the error itself is shown by <ChatError> / onError
    send(input).catch(() => setDraft(input))
    textareaRef.current?.focus()
  }, [busy, draft, send])

  const focus = React.useCallback(() => textareaRef.current?.focus(), [])

  const addKeyDownHandler = React.useCallback((handler: ChatInputKeyHandler) => {
    keyHandlers.current.add(handler)
    return () => {
      keyHandlers.current.delete(handler)
    }
  }, [])

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    for (const handler of keyHandlers.current) {
      if (handler(e)) {
        e.preventDefault()
        return
      }
    }
    if (submitOnEnter && e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      submit()
    }
  }

  const context = React.useMemo(
    () => ({ draft, setDraft, submit, focus, addKeyDownHandler, disabled: busy }),
    [draft, submit, focus, addKeyDownHandler, busy],
  )

  return (
    <ChatInputContext.Provider value={context}>
      <div className={cn('relative w-full min-w-64 rounded-2xl border bg-background px-3 py-2 shadow-xs focus-within:ring-1 focus-within:ring-ring', className)}>
        <textarea
          ref={textareaRef}
          rows={1}
          value={draft}
          placeholder={placeholder}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onKeyDown}
          className={'block w-full resize-none bg-transparent outline-none placeholder:text-muted-foreground py-1'}
        />
        <div className={'flex items-center gap-2 pt-1'}>
          <div className={'flex flex-1 items-center gap-2'}>{children}</div>
          {busy
            ? <Button type={'button'} size={'icon'} variant={'outline'} aria-label={'Stop'} onClick={cancel}>
              <SquareIcon />
            </Button>
            : <Button type={'button'} size={'icon'} aria-label={'Send'} disabled={!draft.trim()} onClick={submit}>
              <SendHorizonalIcon />
            </Button>}
        </div>
      </div>
    </ChatInputContext.Provider>
  )
}

export default ChatInput
