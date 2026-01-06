import React from 'react'
import ReactJson from '@microlink/react-json-view'
import { AiAssistVoicePrompt } from './AiAssistVoicePrompt.tsx'
import './AiAssist.scss'

export const AiAssistPanel = () => {
  const [completions, setCompletions] = React.useState([])

  return (
    <div className={'AiAssistPanel'}>
      <div className={'AiAssist-TextPrompt'}>
        <input type='text' placeholder='Type your message here' />
      </div>

      <div className={'AiAssist-VoicePrompt'}>
        <AiAssistVoicePrompt onResponse={(data) => setCompletions(data)} />
      </div>

      <div>{completions && <ReactJson src={completions} />}</div>
    </div>
  )
}
