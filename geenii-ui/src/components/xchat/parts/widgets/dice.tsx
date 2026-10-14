import React from 'react'
import { DicesIcon } from 'lucide-react'
import { Button } from '@/components/ui/button.tsx'
import { WidgetRendererProps } from '@/components/xchat/chat.types.ts'
import { useReducedMotion } from './use-reduced-motion.ts'

const FACES = ['⚀', '⚁', '⚂', '⚃', '⚄', '⚅']

const ROLL_MS = 700

const randomValues = (count: number) => Array.from({ length: count }, () => 1 + Math.floor(Math.random() * 6))

/**
 * geenii.dice — data: { count? = 1 (max 10), values? (pre-rolled results, 1–6) }
 * Rolls once on display (to `values` if given); "Roll" rolls again in the browser.
 */
export const DiceWidget = ({ data }: WidgetRendererProps<{ count?: number; values?: number[] } | null>) => {
  const reduced = useReducedMotion()
  const preset = Array.isArray(data?.values) && data.values.length > 0 && data.values.every((v) => v >= 1 && v <= 6)
    ? data.values.slice(0, 10).map(Math.floor) : null
  const count = preset?.length ?? Math.min(10, Math.max(1, data?.count ?? 1))
  const [result, setResult] = React.useState(() => preset ?? randomValues(count))
  const [shown, setShown] = React.useState(result)
  const [rolling, setRolling] = React.useState(false)

  // shuffle the faces for a moment, then settle on the result
  React.useEffect(() => {
    if (reduced) {
      setShown(result)
      return
    }
    setRolling(true)
    const shuffle = setInterval(() => setShown(randomValues(result.length)), 80)
    const settle = setTimeout(() => {
      clearInterval(shuffle)
      setShown(result)
      setRolling(false)
    }, ROLL_MS)
    return () => {
      clearInterval(shuffle)
      clearTimeout(settle)
    }
  }, [result, reduced])

  return (
    <div className={'inline-flex items-center gap-3 rounded-md border px-3 py-2'}>
      <div className={`flex gap-1 text-5xl leading-none ${rolling ? 'animate-bounce' : ''}`}
           aria-label={rolling ? 'Rolling…' : `Rolled ${result.join(', ')}`}>
        {shown.map((v, i) => <span key={i}>{FACES[v - 1]}</span>)}
      </div>
      <div className={'flex flex-col items-start gap-1'}>
        {result.length > 1 && (
          <span className={'text-sm tabular-nums text-muted-foreground'}>{rolling ? '…' : `= ${result.reduce((a, b) => a + b, 0)}`}</span>
        )}
        <Button variant={'outline'} size={'sm'} disabled={rolling} onClick={() => setResult(randomValues(count))}>
          <DicesIcon />Roll
        </Button>
      </div>
    </div>
  )
}
