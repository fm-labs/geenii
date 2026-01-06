import React, { ChangeEventHandler, KeyboardEventHandler } from 'react'
import { SendHorizonal } from 'lucide-react'

interface ChatInputProps {
  onChange?: (data: any) => void,
  onSubmit?: (data: any) => Promise<void>
}

const ChatInput = (props: ChatInputProps) => {

  const [input, setInput] = React.useState<string>('')

  const handleInputChange: ChangeEventHandler<HTMLTextAreaElement> = (e) => {
    const target = e.target as HTMLTextAreaElement
    setInput(target.value)

    // get content height and set textarea height
    target.style.height = 'auto' // reset height
    target.style.height = `${target.scrollHeight}px` // set new height
    // console.log(">> TEXTAREA HEIGHT", target.scrollHeight, target.style.height)
    // console.log(">> TEXTAREA VALUE", target.value)
    // console.log(">> TEXTAREA", target)

    if (props?.onChange) {
      props.onChange(target.value)
    }
  }

  const handleSubmit = () => {
    // handle submission logic here
    if (props?.onSubmit) {
      props.onSubmit(input)
    } else {
      console.warn("No onSubmit handler provided")
    }
  }

  const handleInputKeyDown: KeyboardEventHandler<HTMLTextAreaElement> = (e) => {
    if (e.key.toLowerCase()==='enter' && e.shiftKey===false) {
      e.preventDefault()
      e.stopPropagation()
      handleSubmit()
    }
  }

  return (
    <div className={'Chat-input'}>
      <div className={'Chat-input-field'}>
                        <textarea placeholder={'What\'s up?'}
                                  rows={1}
                                  value={input}
                                  onKeyDown={handleInputKeyDown}
                                  onChange={handleInputChange} />
      </div>
      <div className={'Chat-input-buttons'}>
        <div>
          {/*FEATURE_CHAT_FILES_ENABLED && <button onClick={() => setShowFilesPopup(true)}>Add Files</button>*/}
          {/*FEATURE_CHAT_TOOLS_ENABLED && <button>Add Tools</button>*/}
          {/*FEATURE_VOICE_RECORDING_ENABLED && <VoiceRecorder onAudioRecorded={handleAudioRecorded} />*/}
        </div>
        <div>
          <button className={'border-none'} disabled={input.trim()===''}
                  onClick={handleSubmit}><SendHorizonal />
          </button>
        </div>
      </div>
    </div>
  )
}

export default ChatInput