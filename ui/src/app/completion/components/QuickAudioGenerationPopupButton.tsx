import React from "react";
import Popup from "../../../ui/Popup.tsx";
import QuickCompletion from "./QuickCompletion.tsx";
import { AppContext } from "../../../context/AppContext.tsx";
import { Button } from "../../../ui";
import useNotification from '../../../hooks/useNotification.ts'

const QuickAudioGenerationPopupButton = ({ modelName }) => {
    const [isOpen, setIsOpen] = React.useState(false);
    const [audioUrl, setAudioUrl] = React.useState("");
    const [isThinking, setIsThinking] = React.useState(false);
    const notify = useNotification();
    const context = React.useContext(AppContext);
    if (!context) {
        throw new Error("AppContext is not provided");
    }

    const handleSubmit = async (text: string) => {
        console.log(">> SUBMIT INPUT", text);
        setAudioUrl("")
        if (text.trim()==="") {
            console.warn(">> EMPTY INPUT, NOT SUBMITTING");
            return; // do not submit empty input
        }

        setIsThinking(true);
        const response = await context.xaiApi.generateAudio({ model: modelName, text })
          .catch((err) => {
              console.error('Error generating audio:', err)
              notify.error('Error generating audio: ' + err.message)
          })
            .finally(() => {
                setIsThinking(false);
            });
        console.log(">> XAI RESPONSE", response);
        if (!response || !response.output || response.output.length === 0) {
            console.warn(">> NO OUTPUT FROM XAI RESPONSE");
            return;
        }

        const output = response?.output[0]
        let audioUrl;
        if (output?.url) {
            audioUrl = output.url;
        } else if (output?.base64) {
            // Convert base64 to data URL
            audioUrl = `data:audio/png;base64,${output.base64}`;
        }
        setAudioUrl(audioUrl)
    };

    const handleClose = () => {
        setIsOpen(false);
        setAudioUrl("");
        setIsThinking(false);
    }

    return (
        <>
            <Button
                onClick={() => setIsOpen(true)}
            >Convert Text to Speech
            </Button>

            {/* Popup for Quick Generator */}
            <Popup show={isOpen} onClose={handleClose} title="Quick Audio Generation" size="md"
                   showCloseButton={true}>
                <div>
                    <h2 className="text-2xl font-bold mb-4">Text-to-Speech</h2>
                    <p className="text-gray-600 mb-4">
                        Quickly generate an audio from a text input.
                    </p>
                    {isThinking ? "Painting ..." : ""}
                    <QuickCompletion defaultPrompt={`The lazy brown fox jumped over the bridge`} onSubmit={handleSubmit} />
                </div>

                <div className="mt-8">
                    {isThinking && (
                        <p className="text-gray-500 mb-4">Generating audio...</p>
                    )}
                    {audioUrl && (
                        <div className="mb-4">
                            <audio
                                controls={true}
                                autoPlay={true}
                                title="Generated"
                                className="w-full h-auto rounded-lg shadow-md"
                            >
                                <source src={audioUrl} type="audio/wav" />
                                Your browser does not support the audio element.
                            </audio>
                            <button className="mt-2 text-blue-500 hover:underline"
                                    onClick={() => {
                                        const link = document.createElement('a');
                                        link.href = audioUrl;
                                        link.download = 'generated-audio.wav';
                                        document.body.appendChild(link);
                                        link.click();
                                        document.body.removeChild(link);
                                    }
                            }>Download Audio</button>
                        </div>
                    )}
                    {/*<p className="text-gray-700 min-h-8 max-h-16 overflow-y-scroll">{audioUrl || ""}</p>*/}
                </div>
            </Popup>
        </>
    );
};

export default QuickAudioGenerationPopupButton;
