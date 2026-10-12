import React from 'react'
import { FEATURE_CHAT_PROMPT_SUGGESTIONS_ENABLED, PROMPT_INPUT_SUGGESTIONS } from '@/constants.ts'

const ChatPromptSuggestions = () => {

  if (!FEATURE_CHAT_PROMPT_SUGGESTIONS_ENABLED) {
    return null
  }

  const [input, setInput] = React.useState<string>('')

  return (
    <div className={'Chat-input-suggestions my-5'}>
      <ul>
        {PROMPT_INPUT_SUGGESTIONS.map((suggestion, idx) => (
          <li key={`s-${idx}`}>
            <button onClick={() => setInput(suggestion)}>{suggestion}</button>
          </li>
        ))}
      </ul>
    </div>
  )
}

export default ChatPromptSuggestions