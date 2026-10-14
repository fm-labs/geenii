import React from 'react'
import { WidgetRendererProps } from '@/components/xchat/chat.types.ts'

type Point = [number, number]

type Game = {
  snake: Point[]
  dir: Point
  nextDir: Point
  food: Point
  score: number
  status: 'ready' | 'running' | 'paused' | 'over'
}

const DIRECTIONS: Record<string, Point> = {
  ArrowUp: [0, -1], w: [0, -1],
  ArrowDown: [0, 1], s: [0, 1],
  ArrowLeft: [-1, 0], a: [-1, 0],
  ArrowRight: [1, 0], d: [1, 0],
}

const same = (a: Point, b: Point) => a[0] === b[0] && a[1] === b[1]

const randomFood = (snake: Point[], size: number): Point => {
  const free: Point[] = []
  for (let x = 0; x < size; x++) for (let y = 0; y < size; y++) {
    if (!snake.some((p) => p[0] === x && p[1] === y)) free.push([x, y])
  }
  return free[Math.floor(Math.random() * free.length)] ?? [0, 0]
}

const newGame = (size: number): Game => {
  const mid = Math.floor(size / 2)
  const snake: Point[] = [[mid, mid], [mid - 1, mid], [mid - 2, mid]]
  return { snake, dir: [1, 0], nextDir: [1, 0], food: randomFood(snake, size), score: 0, status: 'ready' }
}

const tick = (game: Game, size: number): Game => {
  const dir = game.nextDir
  const head: Point = [game.snake[0][0] + dir[0], game.snake[0][1] + dir[1]]
  const eats = same(head, game.food)
  const body = eats ? game.snake : game.snake.slice(0, -1)
  const hitWall = head[0] < 0 || head[1] < 0 || head[0] >= size || head[1] >= size
  if (hitWall || body.some((p) => same(p, head))) return { ...game, dir, status: 'over' }
  const snake = [head, ...body]
  return { ...game, snake, dir, food: eats ? randomFood(snake, size) : game.food, score: game.score + (eats ? 1 : 0) }
}

/** geenii.snake — data: { size? = 16, speed? = 120 ms per step }; focus it, then arrows/WASD to steer, space to start/pause */
export const SnakeWidget = ({ data }: WidgetRendererProps<{ size?: number; speed?: number } | null>) => {
  const size = Math.min(32, Math.max(8, data?.size ?? 16))
  const speed = data?.speed ?? 120
  const [game, setGame] = React.useState(() => newGame(size))
  const [best, setBest] = React.useState(0)

  React.useEffect(() => {
    if (game.status !== 'running') return
    const timer = setInterval(() => setGame((g) => tick(g, size)), speed)
    return () => clearInterval(timer)
  }, [game.status, size, speed])

  React.useEffect(() => setBest((b) => Math.max(b, game.score)), [game.score])

  const onKeyDown = (e: React.KeyboardEvent) => {
    const dir = DIRECTIONS[e.key.length === 1 ? e.key.toLowerCase() : e.key]
    if (dir) {
      e.preventDefault()
      // no turning back into yourself
      setGame((g) => (g.status === 'running' && !same(dir, [-g.dir[0], -g.dir[1]]) ? { ...g, nextDir: dir } : g))
    } else if (e.key === ' ') {
      e.preventDefault()
      setGame((g) => (g.status === 'over' ? { ...newGame(size), status: 'running' }
        : { ...g, status: g.status === 'running' ? 'paused' : 'running' }))
    }
  }

  const cells = new Set(game.snake.map(([x, y]) => y * size + x))
  const headIndex = game.snake[0][1] * size + game.snake[0][0]
  const foodIndex = game.food[1] * size + game.food[0]
  const message = { ready: 'Click, then press space', paused: 'Paused — press space', over: 'GAME OVER — press space', running: null }[game.status]

  return (
    <div className={'inline-flex flex-col gap-1 font-mono text-xs'}>
      <div className={'flex justify-between text-muted-foreground'}>
        <span>SCORE {String(game.score).padStart(3, '0')}</span>
        <span>HI {String(best).padStart(3, '0')}</span>
      </div>
      <div
        tabIndex={0}
        role={'application'}
        aria-label={'Snake game'}
        onKeyDown={onKeyDown}
        onBlur={() => setGame((g) => (g.status === 'running' ? { ...g, status: 'paused' } : g))}
        className={'relative grid w-64 max-w-full cursor-pointer gap-px rounded-md border-2 border-[#33ff33]/40 bg-[#0a0f0a] p-1 outline-none focus:border-[#33ff33]'}
        style={{ gridTemplateColumns: `repeat(${size}, minmax(0, 1fr))` }}
      >
        {Array.from({ length: size * size }, (_, i) => (
          <div key={i} className={`aspect-square rounded-[1px] ${
            i === headIndex ? 'bg-[#aaffaa]' : cells.has(i) ? 'bg-[#33ff33]' : i === foodIndex ? 'bg-red-500' : ''}`} />
        ))}
        {message && (
          <div className={'absolute inset-0 flex items-center justify-center bg-black/60 text-center text-[#33ff33]'}>{message}</div>
        )}
      </div>
    </div>
  )
}
