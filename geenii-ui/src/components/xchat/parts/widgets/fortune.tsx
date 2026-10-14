import React from 'react'
import { WidgetRendererProps } from '@/components/xchat/chat.types.ts'

const FORTUNES = [
  'There are only two hard things in computer science: cache invalidation, naming things and off-by-one errors.',
  'It works on my machine.',
  'A clean working tree is the sign of a sick mind.',
  'Have you tried turning it off and on again?',
  'The agent you are looking for is in another context window.',
  'Today is a good day to write tests. Tomorrow too.',
  'Any sufficiently advanced bug is indistinguishable from a feature.',
  'You will soon receive an unexpected tool call.',
  'Real programmers count from 0.',
  'Do not meddle in the affairs of agents, for they are subtle and quick to hallucinate.',
]

const COW = String.raw`        \   ^__^
         \  (oo)\_______
            (__)\       )\/\
                ||----w |
                ||     ||`

/** Wrap text into lines of at most `width` characters (long words are split) */
const wrap = (text: string, width: number) => {
  const lines: string[] = []
  for (const paragraph of text.split('\n')) {
    let line = ''
    for (let word of paragraph.split(/\s+/).filter(Boolean)) {
      while (word.length > width) {
        if (line) { lines.push(line); line = '' }
        lines.push(word.slice(0, width))
        word = word.slice(width)
      }
      if (line && line.length + 1 + word.length > width) { lines.push(line); line = '' }
      line = line ? `${line} ${word}` : word
    }
    lines.push(line)
  }
  return lines
}

/** The classic cowsay speech bubble around `text` */
export const cowsay = (text: string, width = 40) => {
  const lines = wrap(text, width)
  const w = Math.max(...lines.map((l) => l.length))
  const pad = (l: string) => l.padEnd(w)
  const body = lines.length === 1
    ? [`< ${pad(lines[0])} >`]
    : lines.map((l, i) => {
      const [left, right] = i === 0 ? ['/', '\\'] : i === lines.length - 1 ? ['\\', '/'] : ['|', '|']
      return `${left} ${pad(l)} ${right}`
    })
  return [` ${'_'.repeat(w + 2)}`, ...body, ` ${'-'.repeat(w + 2)}`, COW].join('\n')
}

/** geenii.fortune — data: { fortune? (else a random one), width? = 40 }; a fortune cookie, said by a cow */
export const FortuneWidget = ({ data }: WidgetRendererProps<{ fortune?: string; width?: number } | null>) => {
  const [fortune] = React.useState(() => data?.fortune || FORTUNES[Math.floor(Math.random() * FORTUNES.length)])
  return (
    <pre className={'inline-block max-w-full overflow-x-auto rounded-md border bg-muted/30 p-3 font-mono text-xs leading-tight'}>
      {cowsay(fortune, data?.width ?? 40)}
    </pre>
  )
}
