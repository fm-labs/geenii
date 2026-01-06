import React from "react";
import Popup from "../../ui/Popup.tsx";
import QuickCompletion from "./QuickCompletion.tsx";
import { AppContext } from "../../context/AppContext.tsx";
import { ollamaGenerate } from "../../api/ollama-api.ts";
import { Button } from "../../ui";
import useNotification from '../../hooks/useNotification.ts'

const QuickOllamaTextGenerationPopupButton = ({ modelName }) => {
    const [isOpen, setIsOpen] = React.useState(false);
    const [completion, setCompletion] = React.useState("");
    const context = React.useContext(AppContext);
    const notify = useNotification();
    if (!context) {
        throw new Error("AppContext is not provided");
    }
    if (!modelName || !modelName.startsWith("ollama:")) {
        throw new Error("Model name must be provided and start with 'ollama:'");
    }

    const handleCompletion = async (prompt: string) => {
        console.log(">> SUBMIT INPUT", prompt);
        setCompletion("")
        if (prompt.trim()==="") {
            console.warn(">> EMPTY INPUT, NOT SUBMITTING");
            return; // do not submit empty input
        }

        const ollamaModel = modelName.replace("ollama:", "");
        const response = await ollamaGenerate({ model: ollamaModel, prompt: prompt })
          .catch((err) => {
              console.error('Error generating completion:', err)
              notify.error('Error generating completion: ' + err.message)
          })
            .finally(() => {});
        console.log(">> OLLAMA RESPONSE", response);
        if (!response) {
            console.warn(">> NO OUTPUT FROM OLLAMA RESPONSE");
            return;
        }
        setCompletion(response)
    };

    return (
        <>
            <Button
                onClick={() => setIsOpen(true)}
            >Quick Text Generation
            </Button>

            {/* Popup for Quick Completion */}
            <Popup show={isOpen} onClose={() => setIsOpen(false)} title="Quick Completion" size="md"
                   showCloseButton={true}>
                <div>
                    <h2 className="text-xl font-semibold mb-4">Quick Text Generation</h2>
                    <p className="text-gray-600 mb-4">
                        Quickly generate text completions using the input below. This feature is designed for rapid
                        prototyping and testing.
                    </p>
                    <QuickCompletion onSubmit={handleCompletion} />
                </div>

                <div className="mt-8">
                    <h3 className="text-lg font-semibold mb-2">Generated Completion</h3>
                    <p className="text-gray-700">{completion || "No completion generated yet."}</p>
                </div>
            </Popup>
        </>
    );
};

export default QuickOllamaTextGenerationPopupButton;
