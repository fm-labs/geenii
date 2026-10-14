import { WidgetRenderers } from '@/components/xchat/chat.types.ts'
import { BarChartWidget } from './barchart.tsx'
import { ChoicesWidget } from './choices.tsx'
import { ClockWidget } from './clock.tsx'
import { CodeWidget } from './code.tsx'
import { CountdownWidget } from './countdown.tsx'
import { CsvWidget } from './csv.tsx'
import { DiceWidget } from './dice.tsx'
import { DiffWidget } from './diff.tsx'
import { DonutWidget } from './donut.tsx'
import { ErrorBoundaryTestWidget } from './errorboundarytest.tsx'
import { FileTreeWidget } from './filetree.tsx'
import { FormWidget } from './form.tsx'
import { FunnelWidget } from './funnel.tsx'
import { GaugeWidget } from './gauge.tsx'
import { HeatmapWidget } from './heatmap.tsx'
import { FortuneWidget } from './fortune.tsx'
import { HtmlWidget } from './html.tsx'
import { IframeWidget } from './iframe.tsx'
import { JsonWidget } from './json.tsx'
import { KeyValueWidget } from './keyvalue.tsx'
import { LineChartWidget } from './linechart.tsx'
import { LinksWidget } from './links.tsx'
import { ListWidget } from './list.tsx'
import { MatrixWidget } from './matrix.tsx'
import { PostButtonWidget } from './postbutton.tsx'
import { ProgressWidget } from './progress.tsx'
import { RatingWidget } from './rating.tsx'
import { ScatterWidget } from './scatter.tsx'
import { SnakeWidget } from './snake.tsx'
import { SparklinesWidget } from './sparklines.tsx'
import { StatWidget } from './stat.tsx'
import { StatusWidget } from './status.tsx'
import { StepsWidget } from './steps.tsx'
import { TableWidget } from './table.tsx'
import { TabsWidget } from './tabs.tsx'
import { TerminalWidget } from './terminal.tsx'
import { TimelineWidget } from './timeline.tsx'
import { TreemapWidget } from './treemap.tsx'
import { WeatherWidget } from './weather.tsx'

export { BarChartWidget, ClockWidget, CodeWidget, CountdownWidget, CsvWidget, HtmlWidget, JsonWidget }
export { KeyValueWidget, ListWidget, ProgressWidget, StatWidget, TableWidget }
export { DiffWidget, FileTreeWidget, IframeWidget, LineChartWidget, PostButtonWidget, StepsWidget, TimelineWidget }
export { DiceWidget, FortuneWidget, MatrixWidget, SnakeWidget, TerminalWidget }
export { ChoicesWidget, FormWidget, LinksWidget, RatingWidget, WeatherWidget }
export { DonutWidget, GaugeWidget, HeatmapWidget }
export { ErrorBoundaryTestWidget, TabsWidget }
export { FunnelWidget, ScatterWidget, SparklinesWidget, StatusWidget, TreemapWidget }
export { squarify } from './treemap.tsx'
export { CopyButton } from './copy-button.tsx'
export { formMessage } from './form.tsx'
export { ratingMessage } from './rating.tsx'
export { weatherIcon } from './weather.tsx'
export { messageText, useChatReply } from './use-chat-reply.ts'
export { cowsay } from './fortune.tsx'
export { useReducedMotion } from './use-reduced-motion.ts'
export { safeUrl } from './safe-url.ts'
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
  'geenii.postbutton': PostButtonWidget,
  'geenii.choices': ChoicesWidget,
  'geenii.form': FormWidget,
  'geenii.links': LinksWidget,
  'geenii.tabs': TabsWidget,
  'geenii.rating': RatingWidget,
  'geenii.weather': WeatherWidget,
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
  'geenii.donut': DonutWidget,
  'geenii.gauge': GaugeWidget,
  'geenii.heatmap': HeatmapWidget,
  'geenii.scatter': ScatterWidget,
  'geenii.funnel': FunnelWidget,
  'geenii.treemap': TreemapWidget,
  'geenii.sparklines': SparklinesWidget,
  'geenii.status': StatusWidget,
  'geenii.timeline': TimelineWidget,
  'geenii.filetree': FileTreeWidget,
  // easter eggs
  'geenii.matrix': MatrixWidget,
  'geenii.terminal': TerminalWidget,
  'geenii.snake': SnakeWidget,
  'geenii.fortune': FortuneWidget,
  'geenii.dice': DiceWidget,
  // development aids
  'geenii.dev.errorboundarytest': ErrorBoundaryTestWidget,
}
