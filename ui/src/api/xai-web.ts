import axios, { AxiosResponse, CreateAxiosDefaults } from 'axios'
import {
    AiAudioGenerationApiRequest,
    AiAudioGenerationApiResponse,
    AiAudioTranscriptionApiRequest,
    AiAudioTranscriptionApiResponse,
    AiAudioTranslationApiRequest, AiAudioTranslationApiResponse,
    AiCompletionApiRequest,
    AiCompletionApiResponse,
    AiImageGenerationApiRequest,
    AiImageGenerationApiResponse,
    AiVideoGenerationApiRequest,
    AiVideoGenerationApiResponse,
    IAiClient,
} from "./xai.types.ts";

interface WebApiClientTransport {
    get: (url: string) => Promise<any>;
    post: (url: string, data: any) => Promise<any>;
}

class AxiosHttpWebApiClientTransport implements WebApiClientTransport {
    private httpClient;

    constructor(httpClient: any) {
        this.httpClient = httpClient;
    }

    async get(url: string): Promise<any> {
        const response: AxiosResponse = await this.httpClient.get(url);
        return response.data;
    }

    async post(url: string, data: any): Promise<any> {
        const response: AxiosResponse = await this.httpClient.post(url, data);
        return response.data;
    }
}

class JsonRpcWebsocketWebApiClientTransport implements WebApiClientTransport {
    private ws: WebSocket;
    private queue: Map<string, (result: any) => void> = new Map();
    private url: string;
    private isConnected: boolean = false;

    constructor(wsUrl: string) {
        this.url = wsUrl;
        this.ws = new WebSocket(wsUrl);
    }

    private onOpen(event: Event) {
        console.log("WebSocket connection opened:", event);
        this.isConnected = true;
    }

    private onMessage(event: MessageEvent) {
        console.log("WebSocket message received:", event.data);
        let message: any;
        try {
            message = JSON.parse(event.data);
        } catch (error) {
            console.error("Error parsing WebSocket message:", error);
            return;
        }

        // json rpc message handling
        if (message?.jsonrpc === '2.0') {
            if (message?.id && this.queue.has(message.id)) {
                const resolve = this.queue.get(message.id);
                resolve(message.result);
                this.queue.delete(message.id);
                console.log("Resolved RPC call:", message);
            }
        } else {
            console.warn("Unknown WebSocket message format:", message);
        }
    }

    private onClose(event: CloseEvent) {
        console.log("WebSocket connection closed:", event);
        this.isConnected = false;
    }

    private onError(event: Event) {
        console.error("WebSocket error:", event);
        this.isConnected = false;
    }

    public rpcCall(method: string, params: any, timeout: number = 20000): Promise<any> {
        return new Promise((resolve, reject) => {
            const requestId = Date.now() + Math.random().toString(16).slice(2);
            const request = {
                jsonrpc: '2.0',
                method,
                params,
                id: requestId
            };
            this.ws.send(JSON.stringify(request));
            // Enqueue the resolver
            this.queue.set(requestId, resolve)
            // Timeout to reject the promise if no response is received
            setTimeout(() => {
                if (this.queue.has(requestId)) {
                    this.queue.delete(requestId)
                    reject(new Error('RPC call timed out'))
                }
            }, timeout)
        });
    }

    public rpcNotify(method: string, params: any): void {
        const request = {
            jsonrpc: '2.0',
            method,
            params
        };
        this.ws.send(JSON.stringify(request));
    }

    async get(url: string): Promise<any> {
        return this.rpcCall(url, {})
    }

    async post(url: string, data: any): Promise<any> {
        return this.rpcCall(url, data)
    }
}


const webApiClient = async (baseUrl: string, config?: CreateAxiosDefaults): Promise<IAiClient> => {

    const defaultConfig: CreateAxiosDefaults = {
        baseURL: baseUrl,
        headers: {
            "Content-Type": "application/json",
        }
    }
    const mergedConfig = { ...defaultConfig, ...config };
    //const httpClient = axios.create(mergedConfig);
    const httpClient = new AxiosHttpWebApiClientTransport(axios.create(mergedConfig));

    async function getInfo(): Promise<any> {
        try {
            const response = await httpClient.get(
              `/api/info`);
            console.log("getInfo RESPONSE", response);
            return response;
        } catch (error) {
            console.error("Error invoking XAI_API:", error);
            throw error;
        }
    }

    async function generateCompletion(request: AiCompletionApiRequest): Promise<AiCompletionApiResponse> {
        try {
            const response = await httpClient.post(
              `/ai/v1/completion`, request);
            console.log("getCompletion RESPONSE", response);
            return response;
        } catch (error) {
            console.error("Error invoking XAI_API:", error);
            throw error;
        }
    }

    async function generateChatCompletion(prompt: string, messages: any[], options: AiCompletionApiRequest): Promise<string> {
        try {
            const response = await httpClient.post(
              `/ai/v1/chat/completion`,
              { prompt, messages, model: options.model, stream: false },
            );
            console.log("getChatCompletion RESPONSE", response);
            return response;
        } catch (error) {
            console.error("Error invoking XAI_API:", error);
            throw error;
        }
    }

    async function generateImage(request: AiImageGenerationApiRequest): Promise<AiImageGenerationApiResponse> {
        try {
            const response = await httpClient.post(
              `/ai/v1/image/generate`, request);
            console.log("generateImage RESPONSE", response);
            return response;
        } catch (error) {
            console.error("Error invoking XAI_API:", error);
            throw error;
        }
    }

    async function generateVideo(request: AiVideoGenerationApiRequest): Promise<AiVideoGenerationApiResponse> {
        try {
            const response = await httpClient.post(
              `/ai/v1/video/generate`, request);
            console.log("generateVideo RESPONSE", response);
            return response;
        } catch (error) {
            console.error("Error invoking XAI_API:", error);
            throw error;
        }
    }

    async function generateAudio(request: AiAudioGenerationApiRequest): Promise<AiAudioGenerationApiResponse> {
        try {
            const response = await httpClient.post(
              `/ai/v1/audio/speech`, request);
            console.log("generateAudio RESPONSE", response);
            return response;
        } catch (error) {
            console.error("Error invoking XAI_API:", error);
            throw error;
        }
    }

    async function generateAudioTranscription(request: AiAudioTranscriptionApiRequest): Promise<AiAudioTranscriptionApiResponse> {
        try {
            const response = await httpClient.post(
              `/ai/v1/audio/transcribe`, request);
            console.log("generateAudioTranscription RESPONSE", response);
            return response;
        } catch (error) {
            console.error("Error invoking XAI_API:", error);
            throw error;
        }
    }


    async function generateAudioTranslation(request: AiAudioTranslationApiRequest): Promise<AiAudioTranslationApiResponse> {
        try {
            const response = await httpClient.post(
              `/ai/v1/audio/translate`, request);
            console.log("generateAudioTranslation RESPONSE", response);
            return response;
        } catch (error) {
            console.error("Error invoking XAI_API:", error);
            throw error;
        }
    }

    const api: IAiClient = {
        getInfo: getInfo,
        generateCompletion: generateCompletion,
        generateChatCompletion: generateChatCompletion,
        generateImage: generateImage,
        generateVideo: generateVideo,
        generateAudio: generateAudio,
        generateAudioTranscription: generateAudioTranscription,
        generateAudioTranslation: generateAudioTranslation,
    };
    return api;
}

export default webApiClient;
