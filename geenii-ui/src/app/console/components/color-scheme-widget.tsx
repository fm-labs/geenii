import { WidgetProps } from '@rjsf/utils'
import { COLOR_SCHEMES, DEFAULT_COLOR_SCHEME } from '@/components/color-schemes.ts'
import { cn } from 'cn'
import * as React from 'react'
import { useTheme } from '@/components/theme-provider.tsx'

/**
 * rjsf widget: picks one of the COLOR_SCHEMES by its swatch. The UI previews the
 * picked scheme until the form is saved (which applies it) or left (which reverts it).
 */
const ColorSchemeWidget = ({ id, value, onChange, disabled, readonly }: WidgetProps) => {
  const selected = value || DEFAULT_COLOR_SCHEME
  const { appearance, previewAppearance } = useTheme()

  // preview while the picked scheme differs from the applied one; saving applies it and ends the preview
  React.useEffect(() => {
    previewAppearance(selected === (appearance.colorScheme || DEFAULT_COLOR_SCHEME) ? null : { colorScheme: selected })
  }, [selected, appearance.colorScheme, previewAppearance])
  React.useEffect(() => () => previewAppearance(null), [previewAppearance])
  return (
    <div id={id} role={'radiogroup'} className={'flex flex-wrap gap-2'}>
      {COLOR_SCHEMES.map((scheme) => {
        const active = scheme.value === selected
        return (
          <button
            key={scheme.value}
            type={'button'}
            role={'radio'}
            aria-checked={active}
            disabled={disabled || readonly}
            onClick={() => onChange(scheme.value)}
            className={cn(
              'flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm transition-colors',
              'hover:bg-accent disabled:opacity-50',
              active ? 'border-foreground/60 bg-accent' : 'border-border',
            )}
          >
            <span className={'size-4 rounded-full border border-black/10'} style={{ background: scheme.swatch }} />
            {scheme.label}
          </button>
        )
      })}
    </div>
  )
}

export default ColorSchemeWidget
