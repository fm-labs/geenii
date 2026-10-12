import {
    AiCompletionApiRequest, AiCompletionApiResponse,
    IAiClient,
} from "./xai.types.ts";
async function getInfo(): Promise<any> {
    try {
        console.log("Invoking XAI_API getInfo");
        throw new Error("NOT IMPLEMENTED");
    } catch (error) {
        console.error("Error invoking XAI_API:", error);
        throw error;
    }
}

export async function generateCompletion(request: AiCompletionApiRequest): Promise<AiCompletionApiResponse> {
    try {
        console.log("Invoking XAI_API with request:", request);
        throw new Error("NOT IMPLEMENTED");
    } catch (error) {
        console.error("Error invoking XAI_API:", error);
        throw error;
    }
}

// export async function generateChatCompletion(prompt: string, messages: any[], options: AiCompletionOptions): Promise<string> {
//     try {
//         throw new Error("NOT IMPLEMENTED");
//     } catch (error) {
//         console.error("Error invoking XAI_API:", error);
//         throw error;
//     }
// }
//
// export async function generateImage(prompt: string, options: AiImageGenerationOptions): Promise<string> {
//     try {
//         throw new Error("NOT IMPLEMENTED");
//     } catch (error) {
//         console.error("Error invoking XAI_API:", error);
//         throw error;
//     }
// }
//
// export async function generateVideo(url: string, options: AiVideoGenerationOptions): Promise<string> {
//     try {
//         throw new Error("NOT IMPLEMENTED");
//     } catch (error) {
//         console.error("Error invoking XAI_API:", error);
//         throw error;
//     }
// }
//
// export async function generateAudio(url: string, options: AiAudioGenerationOptions): Promise<string> {
//     try {
//         throw new Error("NOT IMPLEMENTED");
//     } catch (error) {
//         console.error("Error invoking XAI_API:", error);
//         throw error;
//     }
// }
//
// export async function generateAudioTranscription(url: string, options: AiAudioTranscriptionOptions): Promise<string> {
//     try {
//         throw new Error("NOT IMPLEMENTED");
//     } catch (error) {
//         console.error("Error invoking XAI_API:", error);
//         throw error;
//     }
// }
//
//
// export async function generateAudioTranslation(url: string, options: AiAudioTranslationOptions): Promise<string> {
//     try {
//         throw new Error("NOT IMPLEMENTED");
//     } catch (error) {
//         console.error("Error invoking XAI_API:", error);
//         throw error;
//     }
// }

const api: IAiClient = {
    getInfo: getInfo,
    generateCompletion: generateCompletion,
    // generateChatCompletion: generateChatCompletion,
    // generateImage: generateImage,
    // generateVideo: generateVideo,
    // generateAudio: generateAudio,
    // generateAudioTranscription: generateAudioTranscription,
    // generateAudioTranslation: generateAudioTranslation,
};

export default api;
