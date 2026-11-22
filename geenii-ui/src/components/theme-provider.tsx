import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react"
import { ColorScheme, DEFAULT_COLOR_SCHEME, isColorScheme } from "@/components/color-schemes.ts"

type Theme = "dark" | "light" | "system"
type FontFamily = "system" | "sans-serif" | "serif" | "monospace"

/** The `appearance` user settings (see settings-forms.ts) */
export type Appearance = {
  theme?: Theme
  colorScheme?: ColorScheme
  fontFamily?: FontFamily
  /** root font size in px; everything sized in rem scales with it */
  fontSize?: number
}

type ThemeProviderProps = {
  children: React.ReactNode
  defaultTheme?: Theme
  storageKey?: string
}

type ThemeProviderState = {
  theme: Theme
  setTheme: (theme: Theme) => void
  appearance: Appearance
  /** Apply APPEARANCE (e.g. as loaded from or saved to the user settings), replacing the current one */
  setAppearance: (appearance: Appearance) => void
  /** Temporarily show PREVIEW on top of the applied appearance (not saved); null ends the preview */
  previewAppearance: (preview: Appearance | null) => void
}

const initialState: ThemeProviderState = {
  theme: "system",
  setTheme: () => null,
  appearance: {},
  setAppearance: () => null,
  previewAppearance: () => null,
}

const ThemeProviderContext = createContext<ThemeProviderState>(initialState)

// "system" keeps the app's default font (App.scss)
const FONT_STACKS: Record<FontFamily, string | null> = {
  "system": null,
  "sans-serif": "ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
  "serif": "ui-serif, Georgia, Cambria, 'Times New Roman', Times, serif",
  "monospace": "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Courier New', monospace",
}

const readCache = (key: string): Appearance => {
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return {}
    // older versions stored just the theme name
    if (raw === "light" || raw === "dark" || raw === "system") return { theme: raw }
    const parsed = JSON.parse(raw)
    return parsed && typeof parsed === "object" ? parsed : {}
  } catch {
    return {}
  }
}

const writeCache = (key: string, appearance: Appearance) => {
  try {
    localStorage.setItem(key, JSON.stringify(appearance))
  } catch {
    // storage unavailable: the settings are loaded from the server on the next start anyway
  }
}

export function ThemeProvider({
                                children,
                                defaultTheme = "system",
                                storageKey = "geenii-theme",
                                ...props
                              }: ThemeProviderProps) {
  // cached locally so the UI starts in the right theme before the user settings are loaded
  const [appearance, _setAppearance] = useState<Appearance>(() => readCache(storageKey))
  const [preview, setPreview] = useState<Appearance | null>(null)
  // what's shown: the applied appearance with the preview on top
  const shown = useMemo(() => (preview ? { ...appearance, ...preview } : appearance), [appearance, preview])
  const theme: Theme = shown.theme || defaultTheme

  // theme: follows the OS while it's "system"
  useEffect(() => {
    const root = window.document.documentElement
    const media = window.matchMedia("(prefers-color-scheme: dark)")
    const apply = () => {
      root.classList.remove("light", "dark")
      root.classList.add(theme === "system" ? (media.matches ? "dark" : "light") : theme)
    }
    apply()
    if (theme !== "system") return
    media.addEventListener("change", apply)
    return () => media.removeEventListener("change", apply)
  }, [theme])

  // color scheme: color-schemes.css
  const colorScheme: ColorScheme = isColorScheme(shown.colorScheme) ? shown.colorScheme : DEFAULT_COLOR_SCHEME
  useEffect(() => {
    window.document.documentElement.dataset.colorScheme = colorScheme
  }, [colorScheme])

  // font: unset values fall back to the stylesheet defaults
  useEffect(() => {
    const style = window.document.documentElement.style
    const stack = shown.fontFamily ? FONT_STACKS[shown.fontFamily] : null
    if (stack) style.setProperty("font-family", stack)
    else style.removeProperty("font-family")

    const size = shown.fontSize
    if (typeof size === "number" && size >= 10 && size <= 24) style.setProperty("font-size", `${size}px`)
    else style.removeProperty("font-size")
  }, [shown.fontFamily, shown.fontSize])

  const setAppearance = useCallback((next: Appearance) => {
    writeCache(storageKey, next)
    _setAppearance(next)
  }, [storageKey])

  const previewAppearance = useCallback((next: Appearance | null) => setPreview(next), [])

  const setTheme = useCallback((next: Theme) => {
    _setAppearance((current) => {
      const updated = { ...current, theme: next }
      writeCache(storageKey, updated)
      return updated
    })
  }, [storageKey])

  const value = useMemo(
    () => ({ theme, setTheme, appearance, setAppearance, previewAppearance }),
    [theme, setTheme, appearance, setAppearance, previewAppearance],
  )

  return (
    <ThemeProviderContext.Provider {...props} value={value}>
      {children}
    </ThemeProviderContext.Provider>
  )
}

export const useTheme = () => {
  const context = useContext(ThemeProviderContext)

  if (context === undefined)
    throw new Error("useTheme must be used within a ThemeProvider")

  return context
}
