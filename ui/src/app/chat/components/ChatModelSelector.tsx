import React from 'react'
import { AVAILABLE_MODELS } from '@/constants.ts'
import { ChatContext } from '@/app/chat/components/ChatContext.tsx'
import { AppContext } from '@/context/AppContext.tsx'
import { FilterableSelect } from '@/components/filterable-select.tsx'

const ChatModelSelector = () => {
  const chatContext = React.useContext(ChatContext)
  if (!chatContext) {
    throw new Error('ChatContext is not provided')
  }

  const appContext = React.useContext(AppContext)
  if (!appContext) {
    throw new Error('AppContext is not provided')
  }

  const { apiInfo } = appContext
  const { messages, addMessage, modelName, setModelName, isThinking } = chatContext
  const [showSelector, setShowSelector] = React.useState<boolean>(false)

  const [availableModels, setAvailableModels] = React.useState<string[]>(AVAILABLE_MODELS)

  const handleModelChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    console.log('handleModelChange', e)
    setModelName(e.target.value)
    setShowSelector(false)
  }

  const handleModelClick = (e: React.MouseEvent<HTMLSelectElement>) => {
    e.stopPropagation()
    setShowSelector(false)
  }

  React.useEffect(() => {
    if (apiInfo && apiInfo.models) {
      const modelsFromApi = apiInfo.models.map((m: any) => `${m.provider}:${m.name}`)
      console.log('modelsFromApi', modelsFromApi)
      setAvailableModels(modelsFromApi)
      if (!modelsFromApi.includes(modelName)) {
        setModelName(modelsFromApi[0])
      }
    }
  }, [apiInfo])

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
        <span>🧠</span> <span>{`${modelName}`}</span>
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