import React, {useState} from 'react'
import {AudioFileImporter} from './AudioFileImporter.tsx'
import {AudioPlayerWithWaveform} from './AudioPlayerWithWaveform.tsx'
// import { Box } from '@mui/material'
// import GraphicEqIcon from '@mui/icons-material/GraphicEq'
// import MicNoneIcon from '@mui/icons-material/MicNone'
// import MicIcon from '@mui/icons-material/Mic'
// import IconButton from '@mui/material/IconButton'
// import DownloadIcon from '@mui/icons-material/Download'
// import RestartAltIcon from '@mui/icons-material/RestartAlt'
// import UploadFileIcon from '@mui/icons-material/UploadFile'
import {MicOff, Mic, Download, RotateCcw, Upload} from 'lucide-react'

export interface AudioRecorderProps {
    beforeRecording?: (recorder: MediaRecorder) => void
    afterRecording?: (recorder: MediaRecorder) => void
    audioChanged?: (blob: Blob) => void
    enableAudioImport?: boolean
    enableDownload?: boolean
    enableAudioPlayer?: boolean
}

function IconButton({children, ...props}: any) {
    return (
        <button
            {...props}
            className="p-2 rounded hover:bg-gray-200 transition-colors"
            style={{display: 'inline-flex', alignItems: 'center'}}
        >
            {children}
        </button>
    )
}

export function AudioRecorder({...props}: AudioRecorderProps) {
    const [mediaRecorder, setMediaRecorder] = useState<MediaRecorder>()
    const [audioBlob, setAudioBlob] = useState<Blob>()
    const [isRecording, setIsRecording] = useState<boolean>(false)

    const [showImport, setShowImport] = useState<boolean>(false)

    const startRecording = async () => {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            console.warn("Microphone access is not supported in this environment.");
            alert("Microphone access is not supported in this environment.");
            return
        }

        const stream = await navigator.mediaDevices.getUserMedia({audio: true})
        const recorder = new MediaRecorder(stream)
        setMediaRecorder(recorder)
        if (props?.beforeRecording) {
            props.beforeRecording(recorder)
        }

        setIsRecording(true)
        recorder.start()
    }

    const stopRecording = () => {
        setIsRecording(false)
        if (!mediaRecorder) return

        mediaRecorder.ondataavailable = (e) => {
            setAudioBlob(e.data)
            localStorage.setItem('audioBlob', URL.createObjectURL(e.data))
        }
        mediaRecorder.stop()
        if (props?.afterRecording) {
            props.afterRecording(mediaRecorder)
        }
    }

    const downloadAudio = () => {
        if (audioBlob) {
            const url = URL.createObjectURL(audioBlob)
            const a = document.createElement('a')
            a.style.display = 'none'
            a.href = url
            a.download = 'recordedAudio.wav'
            document.body.appendChild(a)
            a.click()
            window.URL.revokeObjectURL(url)
        }
    }

    const importAudio = (blob: Blob) => {
        setAudioBlob(blob)
        console.info('Audio file imported')
    }

    React.useEffect(() => {
        if (audioBlob && props?.audioChanged) {
            props.audioChanged(audioBlob)
        }
    }, [audioBlob])

    return (
        <div>
            <div
                style={{
                    display: 'flex',
                    flexWrap: 'nowrap',
                    flexDirection: 'row',
                    width: '100%',
                    justifyContent: 'space-between',
                }}
            >
                <div>
                    {!isRecording && (
                        <IconButton color={'error'} onClick={startRecording}>
                            <MicOff/>
                        </IconButton>
                    )}
                    {isRecording && (
                        <IconButton color={'success'} onClick={stopRecording}>
                            <Mic/>
                        </IconButton>
                    )}
                    {isRecording ? <span>Recording...</span> : <span>Not recording</span>}
                </div>
                <div>
                    {audioBlob && (
                        <IconButton
                            onClick={() => setAudioBlob(undefined)}
                            title={'Reset audio'}
                            aria-label={'Reset'}
                        >
                            <RotateCcw/>
                        </IconButton>
                    )}
                    {props.enableAudioImport && (
                        <IconButton
                            onClick={() => setShowImport(!showImport)}
                            title={'Import'}
                            aria-label={'Import'}
                        >
                            <Upload/>
                        </IconButton>
                    )}
                    {props.enableDownload && audioBlob && (
                        <IconButton onClick={downloadAudio} title={'Download'} aria-label={'Download'}>
                            <Download/>
                        </IconButton>
                    )}
                </div>
            </div>
            <div>
        <span>
          {props.enableAudioImport && showImport && <AudioFileImporter onData={importAudio}/>}
        </span>
            </div>
            <div>
        <span>
          {props.enableAudioPlayer && audioBlob && (
              <AudioPlayerWithWaveform audioBlob={audioBlob}/>
          )}
        </span>
            </div>
        </div>
    )
}
