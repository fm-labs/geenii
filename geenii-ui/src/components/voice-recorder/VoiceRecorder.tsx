import React from "react";
import useMicrophone from "./useMicrophone.ts";

interface VoiceRecorderProps {
    onAudioRecorded?: (audioBlob: Blob) => void;
}

const VoiceRecorder = (props: VoiceRecorderProps) => {

    const { isMicrophoneSupported, isRecording, startRecording, stopRecording, audioBlob } = useMicrophone()
    const [audioUrl, setAudioUrl] = React.useState<string | null>(null);

    const handleClick = async () => {
        if (isRecording) {
            handleStopRecording();
        } else {
            handleStartRecording();
        }
    }

    const handleStartRecording = async () => {
        await startRecording();
        setAudioUrl(null); // Reset audio URL when starting a new recording
    }

    const handleStopRecording = () => {
        stopRecording();
        const url = audioBlob ? URL.createObjectURL(audioBlob.current) : null;
        setAudioUrl(url);
        if (props.onAudioRecorded && audioBlob.current) {
            props.onAudioRecorded(audioBlob.current);
        }
    }

    const handlePlayAudio = () => {
        if (audioUrl) {
            const audio = new Audio(audioUrl);
            audio.play().catch((error) => {
                console.error("Error playing audio:", error);
            });
        } else {
            console.warn("No audio URL available to play.");
        }
    }

    React.useEffect(() => {
        if (!isMicrophoneSupported()) {
            console.warn("Microphone access is not supported in this environment.");
            alert("Microphone access is not supported in this environment.");
        }
    }, [isMicrophoneSupported]);

    // React.useEffect(() => {
    //     const timer = setInterval(() => {
    //         if (isRecording && audioBlob.current) {
    //             console.info("Audio blob is ready");
    //             const url = URL.createObjectURL(audioBlob.current);
    //             setAudioUrl(url);
    //         }
    //     }, 1000); // Check every second if recording is in progress
    //
    //     return () => clearTimeout(timer);
    // }, [isRecording, audioBlob]);

    return (
        <>
            <button onClick={() => handleClick()}>
                {isRecording ? "Stop Recording" : "Start Recording"}
            </button>
            <button onClick={() => handlePlayAudio()}>Play</button>
            {/*audioUrl && (
                <div>
                    <audio controls>
                        <source src={audioUrl} type="audio/wav" />
                        Your browser does not support the audio element.
                    </audio>
                    <a href={audioUrl} download="recordedAudio.wav">Download {audioUrl}</a>
                </div>
            )*/}
        </>
    );
};

export default VoiceRecorder;
