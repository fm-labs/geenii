import { WidgetRendererProps } from '@/components/xchat/chat.types.ts'
import { safeUrl } from './safe-url.ts'

type State = 'up' | 'degraded' | 'down' | 'maintenance' | 'unknown'

type StatusItem = { name: string; status?: State; description?: string; uptime?: number; history?: (State | null)[]; url?: string }

type StatusData = { title?: string; items: StatusItem[] }

const STATES: Record<State, { label: string; color: string }> = {
  up: { label: 'Operational', color: 'rgb(22 163 74)' }, // green-600
  degraded: { label: 'Degraded', color: 'rgb(245 158 11)' }, // amber-500
  down: { label: 'Down', color: 'var(--destructive)' },
  maintenance: { label: 'Maintenance', color: 'var(--chart-2)' },
  unknown: { label: 'Unknown', color: 'var(--muted-foreground)' },
}

// hasOwnProperty, not `in`: 'toString' is in every object
const stateOf = (s: unknown): State =>
  (typeof s === 'string' && Object.prototype.hasOwnProperty.call(STATES, s) ? s as State : 'unknown')

const MAX_HISTORY = 60

/** The headline: the worst state of all items */
const summary = (items: StatusItem[]) => {
  const count = (s: State) => items.filter((i) => stateOf(i.status) === s).length
  const [down, degraded, maintenance] = [count('down'), count('degraded'), count('maintenance')]
  if (down) return { text: `${down} ${down === 1 ? 'system' : 'systems'} down`, state: 'down' as State }
  if (degraded) return { text: `${degraded} ${degraded === 1 ? 'system' : 'systems'} degraded`, state: 'degraded' as State }
  if (maintenance) return { text: `${maintenance} in maintenance`, state: 'maintenance' as State }
  if (count('up') === items.length) return { text: 'All systems operational', state: 'up' as State }
  return { text: 'Status unknown', state: 'unknown' as State }
}

/**
 * geenii.status — data: { title?, items: { name, status?, description?, uptime?, history?, url? }[] }
 * A status page: one row per service with a coloured dot, an optional uptime percentage and
 * an optional history bar (oldest first, at most the last 60 entries; null for no data).
 * status / history entries: 'up' | 'degraded' | 'down' | 'maintenance' | 'unknown'.
 */
export const StatusWidget = ({ data }: WidgetRendererProps<StatusData | null>) => {
  const items = (Array.isArray(data?.items) ? data.items : []).filter((i): i is StatusItem => typeof i?.name === 'string')
  if (items.length === 0) return <div className={'text-sm text-muted-foreground'}>No services</div>
  const head = summary(items)

  return (
    <div className={'max-w-lg rounded-md border'}>
      <div className={'flex items-center gap-2 border-b px-3 py-2'}>
        <span className={'size-2.5 shrink-0 rounded-full'} style={{ background: STATES[head.state].color }} />
        <span className={'font-medium'}>{data?.title ?? head.text}</span>
        {data?.title && <span className={'ml-auto text-xs text-muted-foreground'}>{head.text}</span>}
      </div>
      <ul className={'divide-y'}>
        {items.map((item, i) => {
          const state = stateOf(item.status)
          const href = item.url ? safeUrl(item.url)?.href : null
          const history = Array.isArray(item.history) ? item.history.slice(-MAX_HISTORY) : []
          return (
            <li key={i} className={'px-3 py-2 text-sm'}>
              <div className={'flex items-center gap-2'}>
                <span className={'size-2 shrink-0 rounded-full'} style={{ background: STATES[state].color }} />
                {href
                  ? <a href={href} target={'_blank'} rel={'noopener noreferrer'} className={'truncate underline-offset-2 hover:underline'}>{item.name}</a>
                  : <span className={'truncate'}>{item.name}</span>}
                <span className={'ml-auto shrink-0 text-xs text-muted-foreground'}>
                  {Number.isFinite(item.uptime) && <span className={'tabular-nums'}>{+item.uptime!.toFixed(2)}% · </span>}
                  <span style={{ color: state === 'up' || state === 'unknown' ? undefined : STATES[state].color }}>{STATES[state].label}</span>
                </span>
              </div>
              {item.description && <div className={'ml-4 mt-0.5 text-xs text-muted-foreground'}>{item.description}</div>}
              {history.length > 0 && (
                <div className={'ml-4 mt-1.5 flex h-5 gap-px'} role={'img'}
                     aria-label={`${item.name} history: ${history.filter((h) => stateOf(h) === 'up').length} of ${history.length} up`}>
                  {history.map((h, j) => (
                    <span key={j} className={'min-w-0.5 flex-1 rounded-[1px]'} title={h == null ? 'No data' : STATES[stateOf(h)].label}
                          style={{ background: h == null ? 'var(--muted)' : STATES[stateOf(h)].color }} />
                  ))}
                </div>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}
