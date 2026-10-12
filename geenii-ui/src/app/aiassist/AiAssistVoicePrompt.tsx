import React, { useState } from 'react'
import { AudioRecorder } from './AudioRecorder.tsx'
import { XAI_API_URL } from '@/constants.ts'

export interface AiAssistVoicePromptProps {
  onResponse?: (response: any) => void
  showProcessButton?: boolean
  showProcessingState?: boolean
}

export const AiAssistVoicePrompt = ({ ...props }: AiAssistVoicePromptProps) => {
  const [audioBlob, setAudioBlob] = React.useState<Blob>()
  const [transcript, setTranscript] = useState<string>()
  const [isRecording, setIsRecording] = useState<boolean>(false)

  const [isProcessing, setIsProcessing] = useState<boolean>(false)

  const transcribeAudio = async () => {
    console.log('transcribe audio')
    if (audioBlob) {
      const timestamp = new Date().valueOf()
      const formData = new FormData()
      formData.append('input_blob', audioBlob, `recordedOrder${timestamp}.wav`)

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


        const response = await fetch(XAI_API_URL + `api/v1/ai/audio/transcribe`, {
          method: 'POST',
          body: formData,
        })
        console.info('Upload successful')
        console.log('Success uploading file', response)
        const data = await response.json()
        console.log('UPLOAD:RESPONSE', data)
        setTranscript(data?.output_text)

        // Call parent component callback
        if (props?.onResponse) {
          props.onResponse(data)
        }
      } catch (error) {
        console.error('Error uploading file', error)
        //toast.error('Upload failed')
      } finally {
        setIsProcessing(false)
        //setAudioBlob(null)
        setTranscript('')
      }
    } else {
      console.warn('No audio blob to transcribe')
    }
  }

  React.useEffect(() => {
    console.log("Audio blob changed", audioBlob)
    transcribeAudio()
  }, [audioBlob])

  return (
    <div>
      <AudioRecorder
        beforeRecording={() => setIsRecording(true)}
        afterRecording={() => {
          console.log('After recording')
          setIsRecording(false)
          //transcribeAudio()
        }}
        audioChanged={(blob) => setAudioBlob(blob)}
        enableAudioImport={false}
        enableDownload={false}
        enableAudioPlayer={true}
      />
      {/*isRecording ? <p>Audio recorder is recording...</p> : <p>Not recording</p>*/}
      {props.showProcessButton && !isRecording && !isProcessing && audioBlob
        && <button onClick={transcribeAudio}>Process</button>}
      {props.showProcessingState && isProcessing && (
        <div>
          Processing audio, please wait...
        </div>
      )}
      {/*transcript && (
        <div>
          <h3>Transcript</h3>
          <p>{transcript}</p>
        </div>
      )*/}
      {/*<TextToSpeech text={transcript} />*/}
    </div>
  )
}
