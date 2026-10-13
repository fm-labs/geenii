import React from 'react'
import { AppContext } from '@/context/app-context.tsx'
import { FilterableSelect } from '@/components/filterable-select.tsx'
import { useChat, useChatActions, useChatBackend } from '@/components/xchat/chat-context.tsx'

/**
 * Model picker. Only shown if the backend lets the client choose the model (capabilities.models).
 * Without `models`, the models reported by the API (AppContext.apiInfo.models) are offered.
 */
const ChatModelSelector = ({ models, className }: { models?: string[]; className?: string }) => {
  const { setModel } = useChatActions()
  const model = useChat((s) => s.model)
  const appContext = React.useContext(AppContext)

  const options = React.useMemo(() => {
    const ids = models ?? (appContext?.apiInfo?.models ?? []).map((m: any) => `${m.provider}:${m.name}`)
    return ids.map((id: string) => ({ value: id, label: id }))
  }, [models, appContext?.apiInfo])

  const supported = useChatBackend().capabilities.models

  // pick the first available model if none (or an unavailable one) is set
  React.useEffect(() => {
    if (supported && options.length > 0 && !options.some((o) => o.value === model)) {
      setModel(options[0].value)
    }
  }, [supported, options, model, setModel])

  if (!supported || options.length === 0) return null

  return (
    <div className={className}>
      <FilterableSelect
        options={options}
        value={model}
        onChange={setModel}
        placeholder={'Choose a model'}
        searchPlaceholder={'Filter…'}
        className={'w-full'}
      />
    </div>
  )
}

export default ChatModelSelector
