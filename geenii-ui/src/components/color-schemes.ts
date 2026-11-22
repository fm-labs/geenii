/** The color schemes defined in color-schemes.css (selected with <html data-color-scheme="...">) */
export const COLOR_SCHEMES = [
  { value: 'orange', label: 'Orange', swatch: 'oklch(0.705 0.213 47.604)' },
  { value: 'neutral', label: 'Neutral', swatch: 'oklch(0.439 0 0)' },
  { value: 'blue', label: 'Blue', swatch: 'oklch(0.623 0.214 259.815)' },
  { value: 'green', label: 'Green', swatch: 'oklch(0.627 0.194 149.214)' },
  { value: 'teal', label: 'Teal', swatch: 'oklch(0.6 0.118 184.704)' },
  { value: 'violet', label: 'Violet', swatch: 'oklch(0.606 0.25 292.717)' },
  { value: 'rose', label: 'Rose', swatch: 'oklch(0.645 0.246 16.439)' },
  { value: 'yellow', label: 'Yellow', swatch: 'oklch(0.795 0.184 86.047)' },
] as const

export type ColorScheme = typeof COLOR_SCHEMES[number]['value']

export const DEFAULT_COLOR_SCHEME: ColorScheme = 'orange'

export const isColorScheme = (value: unknown): value is ColorScheme =>
  COLOR_SCHEMES.some((s) => s.value === value)
