import React from 'react'
import { useApi } from '@/context/api-context.tsx'
import { Appearance, useTheme } from '@/components/theme-provider.tsx'

/**
 * Applies the saved `appearance` user settings to the UI once the API is available.
 * Renders nothing; must be inside both ThemeProvider and ApiProvider.
 */
const AppearanceSettingsSync = () => {
  const { fetchJson } = useApi()
  const { setAppearance } = useTheme()

  React.useEffect(() => {
    let cancelled = false
    ;(fetchJson('/api/v1/settings/user/appearance') as Promise<Appearance>)
      .then((appearance) => { if (!cancelled) setAppearance(appearance) })
      .catch((err) => console.warn('Failed to load the appearance settings:', err))
    return () => { cancelled = true }
  }, [fetchJson, setAppearance])

  return null
}

export default AppearanceSettingsSync
