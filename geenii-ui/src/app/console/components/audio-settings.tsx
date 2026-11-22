import React from 'react'
import Header from '@/components/header.tsx'
import { AudioRecorder } from '@/app/aiassist/AudioRecorder.tsx'
import { AiAssistVoicePrompt } from '@/app/aiassist/AiAssistVoicePrompt.tsx'
import { SettingsFormView } from '@/app/console/components/settings-form-view.tsx'
import { settingsForms } from '@/app/console/settings-forms.ts'

const AudioSettings = () => {
  const [isRecording, setIsRecording] = React.useState(false)
  const [audioBlob, setAudioBlob] = React.useState<Blob>()

  return (
    <div>
      <SettingsFormView namespace="audio" schema={settingsForms["audio"][0]} uiSchema={settingsForms["audio"][1]} />

      <div className={'SettingsSection'}>
        <Header as={'h3'} title={'Microphone'} />
        <p>Click the microphone icon to test audio recording and playback.</p>

        <div className={"mt-2 p-4 bg-accent rounded-xl"}>
          <AudioRecorder
            beforeRecording={() => setIsRecording(true)}
            afterRecording={() => {
              setIsRecording(false)
            }}
            audioChanged={(blob) => setAudioBlob(blob)}
            enableAudioImport={false}
            enableDownload={false}
            enableAudioPlayer={true}
          />
        </div>
      </div>

    </div>
  )
}

export default AudioSettings