import React from 'react'
import QuickTextGenerationPopupButton from '@/app/completion/components/QuickTextGenerationPopupButton.tsx'
import QuickImageGenerationPopupButton from '@/app/completion/components/QuickImageGenerationPopupButton.tsx'
import QuickAudioGenerationPopupButton from '@/app/completion/components/QuickAudioGenerationPopupButton.tsx'
import Header from '@/components/header.tsx'
import Layout from '@/components/layout/layout.tsx'

const CompletionsPage = () => {
  return (
    <Layout>
      <div className={"max-w-1/2 mx-auto p-4 text-center"}>
        <p className={"text-muted-foreground"}>
          Select a generation type to get started quickly.
        </p>
        <div className="flex flex-col gap-4 justify-center mt-8">
          <QuickTextGenerationPopupButton modelName={'ollama:mistral:latest'} />
          <QuickImageGenerationPopupButton modelName={'openai:dall-e-2'} />
          <QuickAudioGenerationPopupButton modelName={'hf:kokoro'} />
        </div>
      </div>
    </Layout>
  )
}

export default CompletionsPage