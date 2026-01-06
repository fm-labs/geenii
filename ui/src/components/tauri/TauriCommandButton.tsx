import { useState } from "react";
import { TauriCommandResponse } from "./tauri.types.ts";
import { useTauri } from "./useTauri.ts";
import { Button } from '../../ui'

interface TauriCommandButtonProps {
    command: string,
    args?: string[],
    label?: string,
    outputFormat?: "plain" | "json"
    onError?: (error: string) => void
    onSuccess?: (response: TauriCommandResponse) => void
}

function TauriCommandButton({ command, args, label, outputFormat} : TauriCommandButtonProps) {
    const { executeCommand } = useTauri()

    const [commandResult, setCommandResult] = useState("");

    async function sendCommand() {
        if (commandResult !== "") {
            setCommandResult(""); // Clear previous result
            return
        }

        //const response: TauriCommandResponse = await invoke("execute_command", { command: command, args: args})
        const response = await executeCommand(command, args);
        console.log("RESPONSE", response)
        if (response.success) {
            if (outputFormat === "json") {
                const json = JSON.parse(response.stdout)
                setCommandResult(JSON.stringify(json, null, 2))
            } else {
                setCommandResult(response.stdout)
            }
        } else {
            setCommandResult('Error: ' + response?.stderr)
        }
    }

    return (
        <>
            <Button onClick={(e) => {
                e.preventDefault();
                sendCommand();
            }}>{label || "Execute Command"}</Button>
            {commandResult && <pre>{commandResult}</pre>}

        </>
    );
}

export default TauriCommandButton;
