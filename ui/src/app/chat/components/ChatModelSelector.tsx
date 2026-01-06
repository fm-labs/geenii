import React from 'react'
import { AVAILABLE_MODELS } from '@/constants.ts'
import { ChatContext } from '@/app/chat/components/ChatContext.tsx'

const ChatModelSelector = () => {
  const chatContext = React.useContext(ChatContext)
  if (!chatContext) {
    throw new Error('ChatContext is not provided')
  }
  const { messages, addMessage, modelName, setModelName, isThinking } = chatContext
  const [showSelector, setShowSelector] = React.useState<boolean>(false)

  const handleModelChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    console.log('handleModelChange', e)
    setModelName(e.target.value)
    setShowSelector(false);
  }

  const handleModelClick = (e: React.MouseEvent<HTMLSelectElement>) => {
    e.stopPropagation();
    setShowSelector(false);
  }


  if (!showSelector) {
    return (
      <div className={'Chat-model-selection mb-2'} onClick={() => setShowSelector(true)}>
            <span className={'inline bg-gray-200 px-2 py-1 rounded-md text-sm text-gray-500'}>
              <span>🧠</span> <span>{`${modelName}`}</span>
            </span>
      </div>
    )
  }

  return (
    <div className={'Chat-model-selector mb-2'}>
      {/*<label htmlFor={'model-select'}>Model:</label>*/}
      <select id={'model-select'} value={modelName} onChange={handleModelChange} onClick={handleModelClick}>
        {AVAILABLE_MODELS.map((model) => (
          <option key={model} value={model}>{model}</option>
        ))}
      </select>
    </div>
  )
}

export default ChatModelSelector