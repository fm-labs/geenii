import React from 'react'
import { WidgetRendererProps } from '@/components/xchat/chat.types.ts'
import { useReducedMotion } from './use-reduced-motion.ts'

const BOOT_LINES = [
  'GEENII BIOS v0.3.4  (C) 1986 fmlabs',
  'Memory test: 640K OK',
  'Detecting agents ......... 1 found',
  'Loading AGENT.EXE',
  'READY.',
]

const SCANLINES = 'repeating-linear-gradient(0deg, rgba(0,0,0,0.3) 0px, rgba(0,0,0,0.3) 1px, transparent 1px, transparent 3px)'

/** geenii.terminal — data: { lines? (a boot sequence), prompt? = 'C:\>', speed? = 30 ms per character } */
export const TerminalWidget = ({ data }: WidgetRendererProps<{ lines?: string[]; prompt?: string; speed?: number } | null>) => {
  const reduced = useReducedMotion()
  const text = (Array.isArray(data?.lines) ? data.lines : BOOT_LINES).join('\n')
  const speed = data?.speed ?? 30
  const [typed, setTyped] = React.useState(0)
  const shown = reduced ? text.length : typed
  const done = shown >= text.length

  React.useEffect(() => {
    if (reduced || typed >= text.length) return
    // pause a little longer at line ends, like a slow machine
    const timer = setTimeout(() => setTyped((n) => n + 1), text[typed] === '\n' ? speed * 8 : speed)
    return () => clearTimeout(timer)
  }, [typed, text, speed, reduced])

  return (
    <div className={'relative overflow-hidden rounded-md border border-[#1a3d1a] bg-[#0a0f0a] p-3'}>
      <pre className={'font-mono text-sm leading-relaxed text-[#33ff33] whitespace-pre-wrap break-words'}
           style={{ textShadow: '0 0 4px rgba(51,255,51,0.6)' }}>
        {text.slice(0, shown)}
        {done && `\n${data?.prompt ?? 'C:\\>'}`}
        <span className={'inline-block h-[1.1em] w-[0.6em] translate-y-[0.15em] bg-[#33ff33] animate-pulse'} aria-hidden={true} />
      </pre>
      <div className={'pointer-events-none absolute inset-0'} style={{ background: SCANLINES }} aria-hidden={true} />
    </div>
  )
}
