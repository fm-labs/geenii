import axios from 'axios'
import { AiCompletionApiRequest } from './xai.types.ts'
import { OLLAMA_API_URL } from '../constants.ts'


const ollamaAxios = axios.create({
  baseURL: OLLAMA_API_URL,
  headers: {
    'Content-Type': 'application/json',
    //'X-Api-Key': `${import.meta.env.VITE_XAI_API_KEY || 'xxx-demo-key-xxx'}`,
  },
})

export async function ollamaGenerate(request: AiCompletionApiRequest): Promise<string> {
  try {
    const response = await ollamaAxios.post(
      `${OLLAMA_API_URL}/api/generate`, { ...request, stream: false })
    console.log('ollamaGenerate RESPONSE', response.data)
    return response.data.response
  } catch (error) {
    console.error('Error invoking Ollama API:', error)
    throw error
  }
}
