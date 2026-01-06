import React, { useState } from "react";


const useMicrophone = () => {

    const TIMESLICE = 1000 // 1 second

    //const [mediaRecorder, setMediaRecorder] = useState<MediaRecorder>()
    //const [stream, setStream] = useState<MediaStream>()
    //const [audioBlob, setAudioBlob] = useState<Blob>()
    const [isRecording, setIsRecording] = useState<boolean>(false)

    const mediaRecorder = React.useRef<MediaRecorder>(null)
    const mediaStream = React.useRef<MediaStream>(null)
    const audioBlob = React.useRef<Blob>(null)
    //const [audioUrl, setAudioUrl] = useState<string>("")

    const isMicrophoneSupported = () => {
        return !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
    }

    const startRecording = async () => {
        if (!isMicrophoneSupported) {
            console.warn("Microphone access is not supported in this environment.");
            alert("Microphone access is not supported in this environment.");
            return
        }
        if (isRecording) {
            console.warn("Already recording. Please stop the current recording before starting a new one.");
            return;
        }

        const stream = await navigator.mediaDevices.getUserMedia({audio: true})
        stream.addEventListener("addtrack", (event) => {
            console.log(`${event.track.kind} track added`);
        });
        stream.addEventListener("removetrack", (event) => {
            console.log(`${event.track.kind} track removed`);
        });

        const recorder = new MediaRecorder(stream)
        recorder.onstart = () => {
            console.info("Recording started");
        }
        recorder.onstop = () => {
            console.info("Recording stopped");
        }
        recorder.onerror = (e) => {
            console.error("Error during recording:", e);
        }
        recorder.ondataavailable = (e) => {
            addAudioData(e.data)
        }
        //setAudioBlob(new Blob()) // Initialize with an empty blob
        //setMediaRecorder(recorder)
        //setStream(stream)
        audioBlob.current = new Blob() // Initialize with an empty blob
        mediaRecorder.current = recorder
        mediaStream.current = stream

        setIsRecording(true)
        mediaRecorder.current.start(TIMESLICE)
    }

    const stopRecording = () => {
        setIsRecording(false)

        if (mediaStream && mediaStream.current) {
            mediaStream.current.getTracks().forEach(track => {
                track.stop();
                console.info("Track stopped:", track);
            })
        }

        if (mediaRecorder && mediaRecorder.current) {
            console.log("Recorder stopped");
            mediaRecorder.current.stop()
        }
    }

    const addAudioData = (blob: Blob) => {
        // append the new audio data to the existing blob
        const oldSize = audioBlob.current.size
        const mergedBlob = new Blob([audioBlob.current, blob], { type: 'audio/wav' })
        const mergedSize = mergedBlob.size
        audioBlob.current = mergedBlob
        console.log("Audio data added. Old size:", oldSize, "New size:", mergedSize)
    }

    return {
        mediaRecorder,
        audioBlob,
        isRecording,
        startRecording,
        stopRecording,
        isMicrophoneSupported
    }
}

export default useMicrophone
