import { useState, useEffect, useCallback, useRef } from 'react'

// ── Types (JSDoc for reference) ────────────────────────────────────────────────
// ContentItem: { type: string, text: string }
// Message:     { id: string, sender_id: string, room_id: string, content: ContentItem[] }

// ── Mock data (replace with real polling logic) ────────────────────────────────
const MOCK_MESSAGES = [
  {
    id: '1',
    sender_id: 'alice',
    room_id: 'general',
    content: [
      { type: 'text', text: 'Hey! Did you see the new deployment went live?' },
      { type: 'text', text: 'Also, the staging env looks good.' },
    ],
  },
  {
    id: '2',
    sender_id: 'bob_dev',
    room_id: 'engineering',
    content: [
      { type: 'text', text: 'PR #412 needs a review when you get a chance 🙏' },
    ],
  },
  {
    id: '3',
    sender_id: 'carol',
    room_id: 'design',
    content: [
      { type: 'text', text: 'Uploaded the new Figma screens to the shared drive.' },
      { type: 'text', text: 'Let me know what you think about the color palette.' },
      { type: 'text', text: 'Also updated the component library docs.' },
    ],
  },
  {
    id: '4',
    sender_id: 'system_bot',
    room_id: 'alerts',
    content: [{ type: 'alert', text: 'Scheduled maintenance window starts at 02:00 UTC.' }],
  },
]

// ── Helpers ────────────────────────────────────────────────────────────────────
function getInitials(sender_id) {
  return sender_id
    .split(/[_\s.-]/)
    .map((p) => p[0]?.toUpperCase() ?? '')
    .slice(0, 2)
    .join('')
}

const AVATAR_COLORS = [
  'bg-violet-500',
  'bg-sky-500',
  'bg-emerald-500',
  'bg-amber-500',
  'bg-rose-500',
  'bg-indigo-500',
  'bg-teal-500',
  'bg-orange-500',
]

function avatarColor(sender_id) {
  let hash = 0
  for (const c of sender_id) hash = (hash * 31 + c.charCodeAt(0)) & 0xffffffff
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length]
}

function typeIcon(type) {
  if (type === 'alert') return '⚠️'
  if (type === 'image') return '🖼️'
  if (type === 'file') return '📎'
  return null
}

function timeAgo() {
  const mins = Math.floor(Math.random() * 59) + 1
  if (mins < 60) return `${mins}m ago`
  return `${Math.floor(mins / 60)}h ago`
}

// ── Bell icon with badge ────────────────────────────────────────────────────────
function BellIcon({ count, onClick, isOpen }) {
  return (
    <button
      onClick={onClick}
      aria-label={`Messages – ${count} unread`}
      className={`
        relative flex items-center justify-center w-10 h-10 rounded-xl
        transition-all duration-200 outline-none
        ${isOpen
        ? 'bg-slate-800 text-white shadow-lg shadow-slate-900/40 scale-95'
        : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
      }
      `}
    >
      {/* Bell SVG */}
      <svg
        width="20"
        height="20"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
        className={`transition-transform duration-300 ${isOpen ? 'rotate-12' : ''}`}
      >
        <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
        <path d="M13.73 21a2 2 0 0 1-3.46 0" />
      </svg>

      {/* Badge */}
      {count > 0 && (
        <span
          className="
    absolute -top-0.5 -right-0.5
    min-w-[18px] h-[18px] px-1
    flex items-center justify-center
    text-[10px] font-bold leading-none
    bg-violet-500 text-white rounded-full
    ring-2 ring-slate-900
    animate-pulse
    "
        >
    {count > 9 ? '9+' : count}
    </span>
      )}
    </button>
  )
}

// ── Single message card ─────────────────────────────────────────────────────────
function MessageCard({ message, isNew, onClick }) {
  const [hovered, setHovered] = useState(false)
  const teaser = message.content[0]
  const extraCount = message.content.length - 1
  const icon = typeIcon(teaser.type)
  const color = avatarColor(message.sender_id)
  const initials = getInitials(message.sender_id)
  const [timestamp] = useState(timeAgo)

  return (
    <button
      onClick={() => onClick?.(message)}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className={`
        w-full text-left px-4 py-3.5
        flex gap-3 items-start
        transition-all duration-150 outline-none
        border-b border-slate-800/60 last:border-b-0
        ${hovered ? 'bg-slate-800/50' : 'bg-transparent'}
        ${isNew ? 'relative' : ''}
        focus-visible:ring-1 focus-visible:ring-violet-500
      `}
    >
      {/* Unread dot */}
      {isNew && (
        <span className="absolute left-1.5 top-1/2 -translate-y-1/2 w-1.5 h-1.5 rounded-full bg-violet-400" />
      )}

      {/* Avatar */}
      <div
        className={`
          flex-shrink-0 w-9 h-9 rounded-xl
          flex items-center justify-center
          text-white text-xs font-semibold tracking-wide
          ${color}
          shadow-md
        `}
      >
        {initials}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline justify-between gap-2 mb-0.5">
  <span className={`text-sm font-semibold truncate ${isNew ? 'text-white' : 'text-slate-300'}`}>
  {message.sender_id}
  </span>
          <span className="text-[11px] text-slate-500 flex-shrink-0 font-mono">{timestamp}</span>
        </div>

        <div className="flex items-center gap-1">
  <span className="text-xs text-slate-500 font-medium truncate">
#{message.room_id}
  </span>
          {extraCount > 0 && (
            <span
              className="text-[10px] text-violet-400 font-semibold bg-violet-500/10 px-1.5 py-0.5 rounded-full flex-shrink-0">
      +{extraCount} more
  </span>
          )}
        </div>

        <p className={`mt-1 text-sm leading-snug line-clamp-2 ${isNew ? 'text-slate-200' : 'text-slate-400'}`}>
          {icon && <span className="mr-1">{icon}</span>}
          {teaser.text}
        </p>
      </div>
    </button>
  )
}

// ── Message detail view ─────────────────────────────────────────────────────────
function MessageDetail({ message, onBack }) {
  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-3 px-4 py-3 border-b border-slate-800">
        <button
          onClick={onBack}
          className="text-slate-400 hover:text-white transition-colors p-1 -ml-1 rounded-lg hover:bg-slate-800"
          aria-label="Back"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
               strokeLinecap="round" strokeLinejoin="round">
            <path d="M19 12H5M12 5l-7 7 7 7" />
          </svg>
        </button>
        <div
          className={`w-8 h-8 rounded-lg flex items-center justify-center text-white text-xs font-semibold ${avatarColor(message.sender_id)}`}
        >
          {getInitials(message.sender_id)}
        </div>
        <div>
          <p className="text-sm font-semibold text-white">{message.sender_id}</p>
          <p className="text-xs text-slate-500">#{message.room_id}</p>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-2.5">
        {message.content.map((item, i) => (
          <div
            key={i}
            className="bg-slate-800/60 rounded-xl px-3.5 py-2.5 border border-slate-700/40"
          >
            {item.type !== 'text' && (
              <span className="text-[10px] uppercase tracking-widest font-bold text-violet-400 block mb-1">
                {item.type}
                </span>
            )}
            <p className="text-sm text-slate-200 leading-relaxed">{item.text}</p>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Panel ───────────────────────────────────────────────────────────────────────
function MessagePanel({ messages, newIds, onMarkAllRead, onMessageClick, selectedMessage, onBack }) {
  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3.5 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <h2 className="text-[15px] font-bold text-white tracking-tight">Inbox</h2>
          {newIds.size > 0 && (
            <span className="text-xs font-semibold bg-violet-500/20 text-violet-300 px-2 py-0.5 rounded-full">
        {newIds.size} new
    </span>
          )}
        </div>
        {newIds.size > 0 && (
          <button
            onClick={onMarkAllRead}
            className="text-xs text-slate-400 hover:text-violet-300 transition-colors font-medium"
          >
            Mark all read
          </button>
        )}
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto">
        {selectedMessage ? (
          <MessageDetail message={selectedMessage} onBack={onBack} />
        ) : messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center px-6 py-12 gap-3">
            <div className="w-12 h-12 rounded-2xl bg-slate-800 flex items-center justify-center text-2xl">
              📭
            </div>
            <p className="text-sm text-slate-400">No new messages</p>
          </div>
        ) : (
          <div>
            {messages.map((msg) => (
              <MessageCard
                key={msg.id}
                message={msg}
                isNew={newIds.has(msg.id)}
                onClick={onMessageClick}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Main component ──────────────────────────────────────────────────────────────
/**
 * MessageInbox
 *
 * Props:
 *   fetchMessages: () => Promise<Message[]>   — async fn that returns latest messages
 *   pollInterval:  number (ms, default 15000) — how often to poll
 */
export default function MessageInbox({
                                       //fetchMessages,
                                       pollInterval = 15_000,
                                     }) {
  const [isOpen, setIsOpen] = useState(false)
  const [messages, setMessages] = useState([])
  const [newIds, setNewIds] = useState(new Set())
  const [selectedMessage, setSelectedMessage] = useState(null)
  const panelRef = useRef(null)
  const knownIds = useRef(new Set())

  const fetchMessages = null

  // Demo: use mock fetcher if none provided
  const fetcher = useCallback(
    fetchMessages ??
    (() => Promise.resolve(MOCK_MESSAGES)),
    [fetchMessages],
  )

  const poll = useCallback(async () => {
    try {
      const fetched = await fetcher()
      const fresh = new Set()
      fetched.forEach((m) => {
        if (!knownIds.current.has(m.id)) fresh.add(m.id)
      })
      fetched.forEach((m) => knownIds.current.add(m.id))
      setMessages(fetched)
      if (fresh.size > 0) setNewIds((prev) => new Set([...prev, ...fresh]))
    } catch (err) {
      console.error('[MessageInbox] poll failed:', err)
    }
  }, [fetcher])

  // Initial + interval polling
  useEffect(() => {
    poll()
    const id = setInterval(poll, pollInterval)
    return () => clearInterval(id)
  }, [poll, pollInterval])

  // Close on outside click
  useEffect(() => {
    if (!isOpen) return

    function handle(e) {
      if (panelRef.current && !panelRef.current.contains(e.target)) {
        setIsOpen(false)
        setSelectedMessage(null)
      }
    }

    document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [isOpen])

  // Close on Escape
  useEffect(() => {
    function handle(e) {
      if (e.key === 'Escape') {
        if (selectedMessage) setSelectedMessage(null)
        else setIsOpen(false)
      }
    }

    document.addEventListener('keydown', handle)
    return () => document.removeEventListener('keydown', handle)
  }, [selectedMessage])

  function markAllRead() {
    setNewIds(new Set())
  }

  function handleMessageClick(msg) {
    setNewIds((prev) => {
      const next = new Set(prev)
      next.delete(msg.id)
      return next
    })
    setSelectedMessage(msg)
  }

  return (
    <div className="relative" ref={panelRef}>
      {/* Trigger */}
      <BellIcon count={newIds.size} onClick={() => setIsOpen((o) => !o)} isOpen={isOpen} />

      {/* Panel */}
      <div
        className={`
          absolute right-0 top-[calc(100%+10px)] z-50
          w-[340px] max-h-[520px]
          bg-slate-900 border border-slate-700/60
          rounded-2xl shadow-2xl shadow-black/60
          flex flex-col overflow-hidden
          origin-top-right
          transition-all duration-200 ease-out
          ${isOpen
          ? 'opacity-100 scale-100 translate-y-0 pointer-events-auto'
          : 'opacity-0 scale-95 -translate-y-2 pointer-events-none'
        }
        `}
        role="dialog"
        aria-label="Message inbox"
      >
        <MessagePanel
          messages={messages}
          newIds={newIds}
          onMarkAllRead={markAllRead}
          onMessageClick={handleMessageClick}
          selectedMessage={selectedMessage}
          onBack={() => setSelectedMessage(null)}
        />
      </div>
    </div>
  )
}

// ── Demo wrapper (remove in production) ────────────────────────────────────────
//   export function MessageInboxDemo() {
//     return (
//       <div className="min-h-screen bg-slate-950 flex items-start justify-end p-6">
//         {/* Fake headerbar */}
//         <div className="fixed top-0 left-0 right-0 h-14 bg-slate-900 border-b border-slate-800 flex items-center justify-end px-6 z-40">
//     <div className="flex items-center gap-2">
//     <div className="w-8 h-8 rounded-full bg-slate-700" />
//     <MessageInbox pollInterval={30_000} />
//     </div>
//     </div>
//     <div className="mt-20 text-slate-600 text-sm">← Headerbar with inbox icon (top-right)</div>
//     </div>
//   );
//   }