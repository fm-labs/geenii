import OllamaModels from '@/app/settings/components/ollama-models.tsx'
import * as React from 'react'

export const AiModelSettingsView = () => {
  return <div>
    <h2 className="text-2xl font-bold mb-4">AI Model Catalog</h2>
    <p className="text-gray-600 mb-4">
      Install and manage AI models available for use within the application.
    </p>
    <OllamaModels />
  </div>
}