import React, { useState } from 'react'
import { AudioRecorder } from './AudioRecorder.tsx'

export interface AiAssistVoicePromptProps {
  onResponse?: (response: any) => void
}

export const AiAssistVoicePrompt = ({ ...props }: AiAssistVoicePromptProps) => {
  const [audioBlob, setAudioBlob] = React.useState<Blob>()
  const [transcript, setTranscript] = useState<string>()
  const [isRecording, setIsRecording] = useState<boolean>(false)

  const [isProcessing, setIsProcessing] = useState<boolean>(false)

  const transcribeAudio = async () => {
    if (audioBlob) {
      const timestamp = new Date().valueOf()
      const formData = new FormData()
      formData.append('file', audioBlob, `recordedOrder${timestamp}.wav`)

      try {
        setIsProcessing(true)
        setTranscript('')
        //@todo handle audio upload
        // const response = await context.xaiApi.transcribeAudio({ model: modelName, text })
        //   .catch((err) => {
        //     console.error('Error generating audio:', err)
        //     notify.error('Error generating audio: ' + err.message)
        //   })
        //   .finally(() => {
        //     setIsThinking(false);
        //   });


        const response = await fetch(`http://voicetransriber-service/openai/configassist`, {
          method: 'POST',
          body: formData,
        })
        console.info('Upload successful')
        console.log('Success uploading file', response)
        const data = await response.json()
        console.log('UPLOAD:RESPONSE', data)
        setTranscript(data?.transcript)

        // Call parent component callback
        if (props?.onResponse) {
          props.onResponse(data)
        }
      } catch (error) {
        console.error('Error uploading file', error)
        //toast.error('Upload failed')
      } finally {
        setIsProcessing(false)
      }
    }
  }

  return (
    <div>
      <AudioRecorder
        beforeRecording={() => setIsRecording(true)}
        afterRecording={() => {
          setIsRecording(false)
          transcribeAudio()
        }}
        audioChanged={(blob) => setAudioBlob(blob)}
        enableAudioImport={true}
        enableDownload={true}
        enableAudioPlayer={true}
      />
      <hr />
      {/*isRecording ? <p>Audio recorder is recording...</p> : <p>Not recording</p>*/}
      {!isRecording && !isProcessing && audioBlob && <button onClick={transcribeAudio}>Process</button>}
      {isProcessing && (
        <div>
          Processing audio, please wait...
        </div>
      )}
      {transcript && (
        <div>
          <h3>Transcript</h3>
          <p>{transcript}</p>
          {/*<TextToSpeech text={transcript} />*/}
        </div>
      )}
    </div>
  )
}
