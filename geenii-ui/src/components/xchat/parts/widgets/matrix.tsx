import React from 'react'
import { WidgetRendererProps } from '@/components/xchat/chat.types.ts'
import { useReducedMotion } from './use-reduced-motion.ts'

const CHARS = 'アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン0123456789'
const FONT_SIZE = 14
const FRAME_MS = 50

/** geenii.matrix — data: { text?, height? = 160, seconds? }; digital rain, stops after `seconds` (default: never) */
export const MatrixWidget = ({ data }: WidgetRendererProps<{ text?: string; height?: number; seconds?: number } | null>) => {
  const canvasRef = React.useRef<HTMLCanvasElement>(null)
  const reduced = useReducedMotion()
  const [showText, setShowText] = React.useState(false)
  const height = data?.height ?? 160
  const seconds = data?.seconds

  React.useEffect(() => {
    const canvas = canvasRef.current
    const ctx = canvas?.getContext('2d')
    if (!canvas || !ctx) return
    canvas.width = canvas.clientWidth
    canvas.height = height
    const drops = Array.from({ length: Math.ceil(canvas.width / FONT_SIZE) }, () => Math.floor(Math.random() * -20))
    ctx.fillStyle = '#000'
    ctx.fillRect(0, 0, canvas.width, canvas.height)

    // one frame: darken the canvas a bit (trails), then draw the next character of every column
    const step = () => {
      ctx.fillStyle = 'rgba(0, 0, 0, 0.08)'
      ctx.fillRect(0, 0, canvas.width, canvas.height)
      ctx.font = `${FONT_SIZE}px monospace`
      drops.forEach((y, i) => {
        ctx.fillStyle = Math.random() > 0.95 ? '#d4ffd4' : '#00ff41'
        ctx.fillText(CHARS[Math.floor(Math.random() * CHARS.length)], i * FONT_SIZE, y * FONT_SIZE)
        drops[i] = y * FONT_SIZE > height && Math.random() > 0.95 ? 0 : y + 1
      })
    }

    if (reduced) {
      for (let i = 0; i < 40; i++) step()
      return
    }
    const end = seconds ? performance.now() + seconds * 1000 : Infinity
    let last = 0
    let raf = 0
    const loop = (t: number) => {
      if (t - last >= FRAME_MS) {
        last = t
        step()
      }
      if (t < end) raf = requestAnimationFrame(loop)
    }
    raf = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf)
  }, [height, seconds, reduced])

  React.useEffect(() => {
    const timer = setTimeout(() => setShowText(true), reduced ? 0 : 2000)
    return () => clearTimeout(timer)
  }, [reduced])

  return (
    <div className={'relative overflow-hidden rounded-md border bg-black'} style={{ height }}>
      <canvas ref={canvasRef} className={'block h-full w-full'} aria-hidden={true} />
      {data?.text && (
        <div className={`absolute inset-0 flex items-center justify-center p-4 text-center font-mono text-lg text-[#00ff41] transition-opacity duration-1000 ${showText ? 'opacity-100' : 'opacity-0'}`}
             style={{ textShadow: '0 0 8px #00ff41, 0 0 2px #000' }}>
          <span className={'bg-black/70 px-2'}>{data.text}</span>
        </div>
      )}
    </div>
  )
}
