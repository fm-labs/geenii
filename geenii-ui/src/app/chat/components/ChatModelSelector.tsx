import React from 'react'
import { ChatContext } from '@/app/chat/components/ChatContext.tsx'
import { FilterableSelect } from '@/components/filterable-select.tsx'
import { modelId, useModels } from '@/hooks/use-models.ts'

const ChatModelSelector = () => {
  const chatContext = React.useContext(ChatContext)
  if (!chatContext) {
    throw new Error('ChatContext is not provided')
  }

  const { modelName, setModelName } = chatContext
  const [showSelector, setShowSelector] = React.useState<boolean>(false)

  const { models, loading, error } = useModels()
  const availableModels = React.useMemo(() => models.map(modelId), [models])

  const handleModelChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    console.log('handleModelChange', e)
    setModelName(e.target.value)
    setShowSelector(false)
  }

  const handleModelClick = (e: React.MouseEvent<HTMLSelectElement>) => {
    e.stopPropagation()
    setShowSelector(false)
  }

  // pick the first available model if none (or an unavailable one) is set
  React.useEffect(() => {
    if (availableModels.length > 0 && !availableModels.includes(modelName)) {
      setModelName(availableModels[0])
    }
  }, [availableModels, modelName, setModelName])

  const OPTIONS = availableModels.map(model => ({ value: model, label: model }))


  // add a hook, that listens for clicks outside of the selector, and closes it when a click is detected
  React.useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as HTMLElement
      if (!target.closest('.Chat-model-selector')) {
        console.log('outside click detected, closing model selector', target)
        setShowSelector(false)
      }
    }
    document.addEventListener('click', handleClickOutside)
    return () => {
      document.removeEventListener('click', handleClickOutside)
    }
  }, [])

  return (
    <div className={'Chat-model-selector py-2 max-w-64'}>
      <span className={showSelector ? 'hidden' : 'inline px-2 py-1 rounded-md text-sm text-gray-500'} onClick={() => setShowSelector(true)}>
        <span>🧠</span> <span>{modelName || (loading ? 'Loading models…' : error ? `No models: ${error}` : 'No model')}</span>
      </span>

      <div className={!showSelector ? 'hidden' : 'max-w-64'}>
        <FilterableSelect
          options={OPTIONS}
          value={modelName}
          onChange={setModelName}
          placeholder="Choose a model"
          searchPlaceholder="Filter…"
          className={'filterable-select'}
        />
      </div>
    </div>
  )
}

export default ChatModelSelector
