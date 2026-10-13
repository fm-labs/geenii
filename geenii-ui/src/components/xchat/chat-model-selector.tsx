import React from 'react'
import { modelId, useModels } from '@/hooks/use-models.ts'
import { FilterableSelect } from '@/components/filterable-select.tsx'
import { useChat, useChatActions, useChatBackend } from '@/components/xchat/chat-context.tsx'

/**
 * Model picker. Only shown if the backend lets the client choose the model (capabilities.models).
 * Without `models`, the server's models (GET /api/v1/ai/models) are offered.
 */
const ChatModelSelector = ({ models, className }: { models?: string[]; className?: string }) => {
  const { setModel } = useChatActions()
  const model = useChat((s) => s.model)
  const supported = useChatBackend().capabilities.models
  const { models: serverModels } = useModels({ enabled: supported && !models })

  const options = React.useMemo(() => {
    const ids = models ?? serverModels.map(modelId)
    return ids.map((id: string) => ({ value: id, label: id }))
  }, [models, serverModels])

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
