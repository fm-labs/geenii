import React from 'react'
import { AiAssistVoicePrompt } from '@/app/aiassist/AiAssistVoicePrompt.tsx'
import { useChatInput } from '@/components/xchat/chat-input.tsx'

/**
 * Voice input add-on for <ChatInput>: records audio, transcribes it (/ai/audio/transcribe)
 * and puts the transcript into the draft.
 */
const ChatVoiceInput = ({ autoSubmit = false }: { autoSubmit?: boolean }) => {
  const { draft, setDraft, submit } = useChatInput()
  const [pendingSubmit, setPendingSubmit] = React.useState(false)

  const onResponse = (data: { output_text?: string }) => {
    if (!data?.output_text) return
    setDraft(draft ? `${draft} ${data.output_text}` : data.output_text)
    if (autoSubmit) setPendingSubmit(true)
  }

  // submit after the draft update has been rendered
  React.useEffect(() => {
    if (pendingSubmit) {
      setPendingSubmit(false)
      submit()
    }
  }, [pendingSubmit, submit])

  return <AiAssistVoicePrompt compact showProcessingState={true} onResponse={onResponse} />
}

export default ChatVoiceInput
