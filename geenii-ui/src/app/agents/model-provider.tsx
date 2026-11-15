import React from 'react'
import { BotIcon, FlaskConicalIcon, WandSparklesIcon } from 'lucide-react'
import { cn } from 'cn'
import anthropicSvg from '@/assets/brands/anthropic.svg'
import openaiSvg from '@/assets/brands/openai.svg'
import ollamaSvg from '@/assets/brands/ollama.svg'

type ProviderIconProps = { size?: number, strokeWidth?: number, className?: string }

/** Renders a monochrome brand SVG in the current text color (via CSS mask) */
const brandIcon = (src: string): React.FC<ProviderIconProps> => ({ size = 24, className }) => (
  <span
    aria-hidden
    className={cn('inline-block shrink-0 bg-current', className)}
    style={{
      width: size, height: size,
      maskImage: `url("${src}")`, WebkitMaskImage: `url("${src}")`,
      maskSize: 'contain', WebkitMaskSize: 'contain',
      maskRepeat: 'no-repeat', WebkitMaskRepeat: 'no-repeat',
      maskPosition: 'center', WebkitMaskPosition: 'center',
    }}
  />
)

export type ModelProviderInfo = {
  /** provider id as used in the model prefix, e.g. "ollama" */
  id: string
  label: string
  /** Brand mark (or a lucide glyph for providers without one) */
  icon: React.ComponentType<ProviderIconProps>
  /** Brand-ish accent used for the badge background */
  color: string
}

const PROVIDERS: Record<string, ModelProviderInfo> = {
  anthropic: { id: 'anthropic', label: 'Anthropic', icon: brandIcon(anthropicSvg), color: '#d97757' },
  openai: { id: 'openai', label: 'OpenAI', icon: brandIcon(openaiSvg), color: '#10a37f' },
  ollama: { id: 'ollama', label: 'Ollama', icon: brandIcon(ollamaSvg), color: '#404040' },
  geenii: { id: 'geenii', label: 'Geenii', icon: WandSparklesIcon, color: '#7c3aed' },
  fake: { id: 'fake', label: 'Fake', icon: FlaskConicalIcon, color: '#64748b' },
}

/** Infers the provider from a model string like "ollama:qwen3:8b"; null when there is no model */
export const modelProvider = (model?: string | null): ModelProviderInfo | null => {
  if (!model) return null
  const idx = model.indexOf(':')
  const id = (idx > 0 ? model.slice(0, idx) : model).trim().toLowerCase()
  return PROVIDERS[id] ?? { id, label: id || 'Unknown', icon: BotIcon, color: '#6b7280' }
}

export const ModelProviderIcon = ({ model, size = 20, className }: {
  model?: string | null
  /** badge edge length in px */
  size?: number
  className?: string
}) => {
  const provider = modelProvider(model)
  if (!provider) return null
  const Icon = provider.icon
  return (
    <span
      title={provider.label}
      aria-label={provider.label}
      className={cn('inline-flex shrink-0 items-center justify-center rounded-full text-white', className)}
      style={{ width: size, height: size, backgroundColor: provider.color }}
    >
      <Icon size={Math.round(size * 0.6)} strokeWidth={2.25} />
    </span>
  )
}
