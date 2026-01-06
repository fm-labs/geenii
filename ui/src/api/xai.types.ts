
export type BaseAiProviderResponse = {
    id: string;
    timestamp: number; // Unix timestamp
    model: string;
    provider: string; // e.g., "openai", "anthropic", etc.
    model_response: any
    error?: string; // Error message if any
}


export type AiCompletionApiRequest = {
    prompt: string;
    model?: string;
    temperature?: number;
    top_p?: number;
    top_k?: number;
    max_tokens?: number;
    stop_sequences?: string[];
    stream?: boolean; // Whether to stream the response
    messages?: { role: string; content: string }[] // For chat-based models
    //response_format?: string; // e.g., "text" or "json"
}

export type AiCompletionApiResponse = BaseAiProviderResponse & {
    output?: any[]; // List of generated text or message objects
}

export type AiImageGenerationApiRequest = {
    prompt: string;
    model?: string;
    size?: string; // e.g., "1024x1024"
    response_format?: string; // e.g., "url" or "base64"
    n?: number; // Number of images to generate
}

export type AiImageGenerationApiResponse = BaseAiProviderResponse & {
    output?: { base64?: string, url?: string }[];
}

export type AiAudioGenerationApiRequest = {
    text: string; // Text for speech generation
    model?: string;
    sample_rate?: number; // e.g., 44100
    duration?: number; // Duration in seconds
    response_format?: string; // e.g., "url" or "base64"
}

export type AiAudioGenerationApiResponse = BaseAiProviderResponse & {
    output?: { base64?: string, url?: string }[];
}

export type AiAudioTranscriptionApiRequest = {
    input: { base64?: string, url?: string }; // URL or base64 audio input
    model?: string;
    language?: string; // e.g., "en-US"
    response_format?: string; // e.g., "text" or "json"
}

export type AiAudioTranscriptionApiResponse = BaseAiProviderResponse & {
    output?: string; // Transcribed text
}


export type AiAudioTranslationApiRequest = {
    input: { base64?: string, url?: string }; // URL or base64 audio input
    model?: string;
    source_language?: string; // e.g., "en"
    target_language?: string; // e.g., "es"
    response_format?: string; // e.g., "text" or "json"
}
export type AiAudioTranslationApiResponse = BaseAiProviderResponse & {
    output?: string; // Transcribed text
}

export type AiVideoGenerationApiRequest = {
    model?: string;
    resolution?: string; // e.g., "1920x1080"
    duration?: number; // Duration in seconds
    frameRate?: number; // Frames per second
}

export type AiVideoGenerationApiResponse = BaseAiProviderResponse & {
    output?: { base64?: string, url?: string }[]; // Video output in base64 or URL format
}

export interface IAiClient {
    getInfo: () => Promise<any>;
    generateCompletion: (request: AiCompletionApiRequest) => Promise<AiCompletionApiResponse>;
    generateChatCompletion?: (prompt: string, messages: { role: string; content: string }[], options?: AiCompletionApiRequest) => Promise<string>;
    generateImage?: (request: AiImageGenerationApiRequest) => Promise<AiImageGenerationApiResponse>;
    generateVideo?: (request: AiVideoGenerationApiRequest) => Promise<AiVideoGenerationApiResponse>;
    generateAudio?: (request: AiAudioGenerationApiRequest) => Promise<AiAudioGenerationApiResponse>;
    generateAudioTranscription?: (request: AiAudioTranscriptionApiRequest) => Promise<AiAudioTranscriptionApiResponse>;
    generateAudioTranslation?: (request: AiAudioTranslationApiRequest) => Promise<AiAudioTranslationApiResponse>;
}


export interface IDockerApiClient {
    getVersion: () => Promise<string>;
    getInfo: () => Promise<any>;
    getModelVersion: () => Promise<string>;
    getMcpVersion: () => Promise<string>;
    getMcpCatalog: () => Promise<any>;
}

// interface XApiClient {
//     generate: (prompt: string, options?: AiGenerateOptions) => Promise<string>;
//
//     // ADMIN API METHODS
//     // // Model management
//     // getModels?: () => Promise<string[]>;
//     // getModelInfo?: (modelName: string) => Promise<any>;
//     //
//     // // Chat management
//     // getChats?: () => Promise<any[]>;
//     // getChat?: (chatId: string) => Promise<any>;
//     // createChat?: (chatName: string) => Promise<any>;
//     // deleteChat?: (chatId: string) => Promise<void>;
//     // addMessageToChat?: (chatId: string, message: any) => Promise<any>;
//     // getMessagesFromChat?: (chatId: string) => Promise<any[]>;
//     // clearChat?: (chatId: string) => Promise<void>;
//     //
//     // // MCP Server management
//     // getMcpServers?: () => Promise<any[]>;
//     // getMcpServerInfo?: (serverId: string) => Promise<any>;
//     // createMcpServer?: (serverConfig: any) => Promise<any>;
//     // deleteMcpServer?: (serverId: string) => Promise<void>;
//     // updateMcpServer?: (serverId: string, serverConfig: any) => Promise<any>;
//     // // MCP Server operations
//     // callMcpServer?: (serverId: string, operation: string, data?: any) => Promise<any>;
//     // promptMcpServer?: (serverId: string, prompt: string, options?: AiGenerateOptions) => Promise<string>;
// }
