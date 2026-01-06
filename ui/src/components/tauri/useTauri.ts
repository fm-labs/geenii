import { invoke } from "@tauri-apps/api/core";
import { TauriCommandResponse } from "./tauri.types.ts";

export async function executeCommand(command: string, args?: string[]): Promise<TauriCommandResponse> {
    try {
        const response: TauriCommandResponse = await invoke("execute_command", { command, args });
        if (response.success) {
            return response;
        } else {
            throw new Error(`Command failed: ${response.stderr}`);
        }
    } catch (error) {
        console.error("Error executing command:", error);
        throw error; // Re-throw to handle in the calling context
    }
}

export const useTauri = () => {
    return {
        invoke,

        // custom tauri commands
        executeCommand
    }
}
