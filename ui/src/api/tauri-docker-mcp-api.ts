import { IDockerApiClient } from "./xai.types.ts";
import { executeCommand } from "../components/tauri/useTauri.ts";

export const getTauriDockerVersion = async () => {
    const response = executeCommand('docker', ['version'])
    return response.then(res => {
        if (res.success) {
            return res.stdout.trim();
        } else {
            throw new Error(`Failed to get Docker version: ${res.stderr}`);
        }
    });
}

export const getTauriDockerInfo = async () => {
    return executeCommand('docker', ['info', '--format', 'json'])
}

export const getTauriDockerMcpVersion = async () => {
    const response = executeCommand('docker', ['mcp', 'version'])
    return response.then(res => {
        if (res.success) {
            return res.stdout.trim();
        } else {
            throw new Error(`Failed to get Docker MCP version: ${res.stderr}`);
        }
    });
}

export const getTauriDockerMcpCatalog = async () => {
    return executeCommand('docker', ['mcp', 'catalog', 'show', 'docker-mcp', '--format', 'json'])
}

export const getTauriDockerModelVersion = async () => {
    const response = executeCommand('docker', ['model', 'version'])
    return response.then(res => {
        if (res.success) {
            return res.stdout.trim();
        } else {
            throw new Error(`Failed to get Docker Model version: ${res.stderr}`);
        }
    });
}

const tauriDockerMcpApi: IDockerApiClient = {
    getVersion: getTauriDockerVersion,
    getInfo: getTauriDockerInfo,
    getMcpVersion: getTauriDockerMcpVersion,
    getMcpCatalog: getTauriDockerMcpCatalog,
    getModelVersion: getTauriDockerModelVersion
}

export default tauriDockerMcpApi;
