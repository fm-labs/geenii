import React from 'react'
import { cn } from 'cn'
import { useChat, useChatBackend } from '@/components/xchat/chat-context.tsx'
import { useChatInput } from '@/components/xchat/chat-input.tsx'
import { ChatCommand } from '@/components/xchat/chat.types.ts'

const normalize = (commands: ChatCommand[]): ChatCommand[] => {
  const seen = new Set<string>()
  const result: ChatCommand[] = []
  for (const c of commands) {
    const command = c.command.replace(/^\/+/, '').trim()
    if (!command || seen.has(command)) continue
    seen.add(command)
    result.push({ ...c, command })
  }
  return result
}

/**
 * The backend's slash commands for the current conversation (empty if the backend has none).
 * Refetched when the backend or the conversation changes.
 */
export const useChatCommands = (): ChatCommand[] => {
  const backend = useChatBackend()
  const contextId = useChat((s) => s.contextId)
  const [commands, setCommands] = React.useState<ChatCommand[]>([])

  React.useEffect(() => {
    if (!backend.listCommands) {
      setCommands([])
      return
    }
    let cancelled = false
    backend.listCommands(contextId)
      .then((list) => { if (!cancelled) setCommands(normalize(list)) })
      .catch((err) => {
        console.warn('Failed to load chat commands', err)
        if (!cancelled) setCommands([])
      })
    return () => {
      cancelled = true
    }
  }, [backend, contextId])

  return commands
}

/** The command typed so far, if the draft is "/<word>" without arguments yet. */
const commandQuery = (draft: string): string | null =>
  draft.startsWith('/') && !/\s/.test(draft) ? draft.slice(1).toLowerCase() : null

/**
 * Input add-on for <ChatInput>: when the draft starts with "/", lists the matching slash commands above the input.
 * Click, Enter or Tab prefills "/<command> "; arrow keys move, Escape closes.
 */
const ChatCommandMenu = ({ className }: { className?: string }) => {
  const { draft, setDraft, focus, addKeyDownHandler } = useChatInput()
  const commands = useChatCommands()
  const [active, setActive] = React.useState(0)
  // the draft at which the user closed the menu with Escape; it reopens once the draft changes
  const [dismissedAt, setDismissedAt] = React.useState<string | null>(null)
  const listRef = React.useRef<HTMLDivElement>(null)

  const query = commandQuery(draft)
  const matches = React.useMemo(
    () => (query === null ? [] : commands.filter((c) => c.command.toLowerCase().startsWith(query))),
    [commands, query],
  )
  const open = matches.length > 0 && dismissedAt !== draft

  React.useEffect(() => setActive(0), [query])

  React.useEffect(() => {
    listRef.current?.querySelector('[aria-selected="true"]')?.scrollIntoView({ block: 'nearest' })
  }, [active, open])

  const select = React.useCallback((command: ChatCommand) => {
    setDraft(`/${command.command} `)
    focus()
  }, [setDraft, focus])

  // the latest state for the key handler, which is registered once
  const state = React.useRef({ open, matches, active, draft, select })
  state.current = { open, matches, active, draft, select }

  React.useEffect(() => addKeyDownHandler((e) => {
    const { open, matches, active, draft, select } = state.current
    if (!open || e.nativeEvent.isComposing) return false
    switch (e.key) {
      case 'ArrowDown':
        setActive((active + 1) % matches.length)
        return true
      case 'ArrowUp':
        setActive((active - 1 + matches.length) % matches.length)
        return true
      case 'Tab':
        select(matches[active])
        return true
      case 'Enter':
        // a fully typed command is sent as is
        if (e.shiftKey || draft === `/${matches[active].command}`) return false
        select(matches[active])
        return true
      case 'Escape':
        setDismissedAt(draft)
        return true
      default:
        return false
    }
  }), [addKeyDownHandler])

  if (!open) return null

  return (
    <div ref={listRef} role={'listbox'} aria-label={'Slash commands'}
         className={cn(
           'absolute bottom-full left-0 right-0 z-20 mb-2 max-h-64 overflow-y-auto rounded-xl border',
           'bg-popover p-1 text-popover-foreground shadow-md',
           className,
         )}>
      {matches.map((command, i) => (
        <button key={command.command} type={'button'} role={'option'} aria-selected={i === active}
                // keep the focus in the textarea
                onMouseDown={(e) => e.preventDefault()}
                onMouseEnter={() => setActive(i)}
                onClick={() => select(command)}
                className={cn(
                  'flex w-full items-baseline gap-3 rounded-md px-3 py-1.5 text-left text-sm',
                  i === active && 'bg-accent text-accent-foreground',
                )}>
          <span className={'shrink-0 font-mono'}>/{command.command}</span>
          {command.description && <span className={'truncate text-xs text-muted-foreground'}>{command.description}</span>}
        </button>
      ))}
    </div>
  )
}

export default ChatCommandMenu
