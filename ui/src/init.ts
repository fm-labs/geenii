import { IAiClient, IDockerApiClient } from "./api/xai.types.ts";

type ApiClientInitializer = (baseUrl: string, config?: any) => Promise<IAiClient>;

export const initWebXapi = async (baseUrl: string): Promise<IAiClient> => {
    console.log("Initializing web XAI");
    const apiBuilder = await import("./api/xai-web.ts");
    if (!apiBuilder?.default) {
        throw new Error("Web XAI API client not found");
    }
    return apiBuilder.default(baseUrl, {});
};

export const initTauriXapi = async (): Promise<IAiClient> => {
    console.log("Initializing Tauri XAI");
    const component = await import("./api/xai-tauri.ts")
    if (!component?.default) {
        throw new Error("Tauri XAI API client not found");
    }
    return component?.default as IAiClient;
};

export const initTauriDockerApiClient = async (): Promise<IDockerApiClient> => {
    console.log("Initializing Tauri Docker Client");
    const component = await import("./components/tauri/tauri-docker-api.ts");
    if (!component?.default) {
        throw new Error("Tauri Docker client not found");
    }
    return component?.default as IDockerApiClient;
};
