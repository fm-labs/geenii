import { WidgetRendererProps } from '@/components/xchat/chat.types.ts'

type Current = {
  temp: number
  condition?: string
  icon?: string
  feels_like?: number
  humidity?: number
  wind?: number
}

type ForecastDay = { day: string; condition?: string; icon?: string; high?: number; low?: number; precip?: number }

type WeatherData = { location?: string; unit?: 'C' | 'F'; wind_unit?: string; current?: Current; forecast?: ForecastDay[] }

// first match wins, so the more specific words come first
const ICONS: [RegExp, string][] = [
  [/thunder|storm/i, '⛈️'],
  [/snow|sleet|blizzard/i, '❄️'],
  [/rain|shower|drizzle/i, '🌧️'],
  [/fog|mist|haze/i, '🌫️'],
  [/partly|mostly sunny|few clouds|scattered/i, '⛅'],
  [/cloud|overcast/i, '☁️'],
  [/wind/i, '💨'],
  [/night/i, '🌙'],
  [/sun|clear/i, '☀️'],
]

/** An emoji for a condition text such as "Partly cloudy" (the sender's `icon` wins) */
export const weatherIcon = (condition?: string, icon?: string) =>
  icon || ICONS.find(([re]) => condition && re.test(condition))?.[1] || '🌡️'

/** "2026-10-15" → "Thu"; any other label stays as it is */
const dayLabel = (day: string) => {
  if (!/^\d{4}-\d{2}-\d{2}/.test(day)) return day
  const date = new Date(day)
  return isNaN(date.getTime()) ? day : date.toLocaleDateString([], { weekday: 'short' })
}

const deg = (value?: number) => (typeof value === 'number' ? `${Math.round(value)}°` : '–')

/**
 * geenii.weather — data: { location?, unit? = 'C', wind_unit? = 'km/h',
 *   current?: { temp, condition?, icon?, feels_like?, humidity?, wind? },
 *   forecast?: { day (label or ISO date), condition?, icon?, high?, low?, precip? (%) }[] }
 * The icon is derived from `condition` unless `icon` is given.
 */
export const WeatherWidget = ({ data }: WidgetRendererProps<WeatherData | null>) => {
  const current = data?.current && typeof data.current.temp === 'number' ? data.current : null
  const forecast = (Array.isArray(data?.forecast) ? data.forecast : []).filter((d): d is ForecastDay => typeof d?.day === 'string')
  const unit = data?.unit === 'F' ? 'F' : 'C'
  const details = current && [
    current.feels_like != null && `Feels like ${deg(current.feels_like)}`,
    current.humidity != null && `Humidity ${Math.round(current.humidity)}%`,
    current.wind != null && `Wind ${Math.round(current.wind)} ${data?.wind_unit ?? 'km/h'}`,
  ].filter(Boolean).join(' · ')

  return (
    <div className={'max-w-md rounded-md border p-3'}>
      {data?.location && <div className={'text-sm font-medium'}>{data.location}</div>}
      {current && (
        <div className={'flex items-center gap-3'}>
          <span className={'text-5xl leading-none'} aria-hidden={true}>{weatherIcon(current.condition, current.icon)}</span>
          <div className={'min-w-0'}>
            <div className={'text-3xl font-semibold tabular-nums'}>{deg(current.temp)}{unit}</div>
            {current.condition && <div className={'text-sm'}>{current.condition}</div>}
            {details && <div className={'text-xs text-muted-foreground'}>{details}</div>}
          </div>
        </div>
      )}
      {forecast.length > 0 && (
        <div className={'mt-3 flex gap-1 overflow-x-auto border-t pt-2'}>
          {forecast.map((day, i) => (
            <div key={i} className={'flex min-w-14 flex-1 flex-col items-center gap-0.5 text-xs'} title={day.condition}>
              <span className={'text-muted-foreground'}>{dayLabel(day.day)}</span>
              <span className={'text-xl leading-none'} aria-label={day.condition}>{weatherIcon(day.condition, day.icon)}</span>
              <span className={'tabular-nums'}>
                {deg(day.high)} <span className={'text-muted-foreground'}>{deg(day.low)}</span>
              </span>
              {day.precip != null && day.precip > 0 && <span className={'tabular-nums text-blue-600 dark:text-blue-400'}>{Math.round(day.precip)}%</span>}
            </div>
          ))}
        </div>
      )}
      {!current && forecast.length === 0 && <div className={'text-sm text-muted-foreground'}>No weather data</div>}
    </div>
  )
}
