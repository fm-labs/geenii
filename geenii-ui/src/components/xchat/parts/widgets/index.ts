import { WidgetRenderers } from '@/components/xchat/chat.types.ts'
import { BarChartWidget } from './barchart.tsx'
import { ClockWidget } from './clock.tsx'
import { CodeWidget } from './code.tsx'
import { CountdownWidget } from './countdown.tsx'
import { CsvWidget } from './csv.tsx'
import { DiceWidget } from './dice.tsx'
import { DiffWidget } from './diff.tsx'
import { FileTreeWidget } from './filetree.tsx'
import { FortuneWidget } from './fortune.tsx'
import { HtmlWidget } from './html.tsx'
import { IframeWidget } from './iframe.tsx'
import { JsonWidget } from './json.tsx'
import { KeyValueWidget } from './keyvalue.tsx'
import { LineChartWidget } from './linechart.tsx'
import { ListWidget } from './list.tsx'
import { MatrixWidget } from './matrix.tsx'
import { ProgressWidget } from './progress.tsx'
import { SnakeWidget } from './snake.tsx'
import { StatWidget } from './stat.tsx'
import { StepsWidget } from './steps.tsx'
import { TableWidget } from './table.tsx'
import { TerminalWidget } from './terminal.tsx'
import { TimelineWidget } from './timeline.tsx'

export { BarChartWidget, ClockWidget, CodeWidget, CountdownWidget, CsvWidget, HtmlWidget, JsonWidget }
export { KeyValueWidget, ListWidget, ProgressWidget, StatWidget, TableWidget }
export { DiffWidget, FileTreeWidget, IframeWidget, LineChartWidget, StepsWidget, TimelineWidget }
export { DiceWidget, FortuneWidget, MatrixWidget, SnakeWidget, TerminalWidget }
export { CopyButton } from './copy-button.tsx'
export { cowsay } from './fortune.tsx'
export { useReducedMotion } from './use-reduced-motion.ts'
export { buildFileTree } from './filetree.tsx'
export { parseCsv } from './csv.tsx'
export { useNow } from './use-now.ts'

/** Built-in widgets. Add or override widgets via <ChatProvider widgets={…}>. */
export const defaultWidgets: WidgetRenderers = {
  'geenii.clock': ClockWidget,
  'geenii.table': TableWidget,
  'geenii.list': ListWidget,
  'geenii.barchart': BarChartWidget,
  'geenii.html': HtmlWidget,
  'geenii.iframe': IframeWidget,
  'geenii.progress': ProgressWidget,
  'geenii.keyvalue': KeyValueWidget,
  'geenii.stat': StatWidget,
  'geenii.code': CodeWidget,
  'geenii.countdown': CountdownWidget,
  'geenii.json': JsonWidget,
  'geenii.csv': CsvWidget,
  'geenii.steps': StepsWidget,
  'geenii.diff': DiffWidget,
  'geenii.linechart': LineChartWidget,
  'geenii.timeline': TimelineWidget,
  'geenii.filetree': FileTreeWidget,
  // easter eggs
  'geenii.matrix': MatrixWidget,
  'geenii.terminal': TerminalWidget,
  'geenii.snake': SnakeWidget,
  'geenii.fortune': FortuneWidget,
  'geenii.dice': DiceWidget,
}
