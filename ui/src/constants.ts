export const APP_NAME = 'g33n11';

export const DEV_MODE = import.meta.env.VITE_DEV_MODE === 'true' && import.meta.env.DEV === true;

//export const DEFAULT_XAI_API_URL = import.meta.env.VITE_XAI_API_URL || 'https://xai.fmlabs.kloudia.cloud/api';
//export const DEFAULT_OLLAMA_API_URL = 'https://xai.fmlabs.kloudia.cloud/proxy/ollama';
export const XAI_API_URL = import.meta.env.VITE_XAI_API_URL || `${window.location.protocol}//${window.location.hostname}:31030/`
export const OLLAMA_API_URL = import.meta.env.VITE_OLLAMA_API_URL || `${window.location.protocol}//${window.location.hostname}:31030/ai/gateway/ollama/`;

export const FEATURE_COMPLETION_ENABLED = import.meta.env.VITE_FEATURE_COMPLETION_ENABLED === 'true' || false;
export const FEATURE_QUICKGEN_BUTTONS_ENABLED = import.meta.env.VITE_FEATURE_FEATURE_QUICKGEN_BUTTONS_ENABLED === 'true' || false;

export const FEATURE_CHAT_ENABLED = import.meta.env.VITE_FEATURE_CHAT_ENABLED === 'true' || false;
export const FEATURE_CHAT_FILES_ENABLED = import.meta.env.VITE_FEATURE_CHAT_FILES_ENABLED === 'true' || false;
export const FEATURE_CHAT_TOOLS_ENABLED = import.meta.env.VITE_FEATURE_CHAT_TOOLS_ENABLED === 'true' || false;
export const FEATURE_CHAT_MODEL_SELECTION_ENABLED = import.meta.env.VITE_FEATURE_CHAT_MODEL_SELECTION_ENABLED === 'true' || false;
export const FEATURE_CHAT_PROMPT_SUGGESTIONS_ENABLED = import.meta.env.VITE_FEATURE_CHAT_PROMPT_SUGGESTIONS_ENABLED === 'true' || false;

export const FEATURE_VOICE_RECORDING_ENABLED = import.meta.env.VITE_FEATURE_VOICE_RECORDING_ENABLED === 'true' || false;
export const FEATURE_VOICE_TRANSCRIPTION_ENABLED = import.meta.env.VITE_FEATURE_VOICE_TRANSCRIPTION_ENABLED === 'true' || false;
export const FEATURE_WIZARD_ENABLED = import.meta.env.VITE_FEATURE_WIZARD_ENABLED === 'true' || false;

export const FEATURE_AGENTS_ENABLED = import.meta.env.VITE_FEATURE_AGENTS_ENABLED === 'true' || false;
export const FEATURE_MCP_ENABLED = import.meta.env.VITE_FEATURE_MCP_ENABLED === 'true' || false;
export const FEATURE_TOOLS_ENABLED = import.meta.env.VITE_FEATURE_TOOLS_ENABLED === 'true' || false;
export const FEATURE_FLOWS_ENABLED = import.meta.env.VITE_FEATURE_FLOWS_ENABLED === 'true' || false;

export const FEATURE_SETTINGS_ENABLED = import.meta.env.VITE_FEATURE_SETTINGS_ENABLED === 'true' || false;

export const FEATURE_TAURI_ENABLED = import.meta.env.VITE_FEATURE_TAURI_ENABLED === 'true' || false;
export const FEATURE_TAURI_XAPI_ENABLED = import.meta.env.VITE_FEATURE_TAURI_XAPI_ENABLED === 'true' || false;

export const CHAT_TYPEWRITER_ENABLED = import.meta.env.VITE_CHAT_TYPEWRITER_ENABLED === 'true' || false;

export const AVAILABLE_MODELS = [
  'ollama:mistral:latest',
  'ollama:llama3.2:3b',
  'ollama:llama3.2:latest',
  'ollama:llama3.1:latest',
  'ollama:llama3:latest',
  'ollama:llama2:latest',
  'openai:gpt-4',
  'openai:gpt-4o-mini',
  'openai:gpt-3.5-turbo',
]
export const PROMPT_INPUT_SUGGESTIONS = [
  'What is the meaning of life?',
  'Tell me a joke',
  'What is the weather like today?',
  'Explain quantum physics in simple terms',
  'What is the capital of France?',
  'How do I make a perfect cup of coffee?',
  'What are the latest news headlines?',
  'Can you recommend a good book to read?',
  'What is the best way to learn programming?',
  'Tell me about the history of the internet.',
]


export const TAURI_UPDATER_CHECK_INTERVAL = 1000 * 60 * 60 // Check for updates every hour