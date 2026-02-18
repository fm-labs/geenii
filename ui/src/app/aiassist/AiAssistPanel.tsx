import React from 'react'
import JsonView from "@/components/json-view.tsx";
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

      <div>{completions && <JsonView src={completions} />}</div>
    </div>
  )
}
