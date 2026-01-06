import React from 'react'
import QuickTextGenerationPopupButton from '@/app/completion/QuickTextGenerationPopupButton.tsx'
import QuickImageGenerationPopupButton from '@/app/completion/QuickImageGenerationPopupButton.tsx'
import QuickAudioGenerationPopupButton from '@/app/completion/QuickAudioGenerationPopupButton.tsx'
import Header from '@/components/header.tsx'
import Layout from '@/components/layout/layout.tsx'
const DeveloperPage = () => {
  return (
    <Layout>
      <div className={"max-w-1/2 mx-auto p-4"}>
        <Header title={'Developer Page'}></Header>

        <h2>Quick Generation</h2>
        <div className="space-x-2">
          <QuickTextGenerationPopupButton modelName={'ollama:mistral:latest'} />
          <QuickImageGenerationPopupButton modelName={'openai:dall-e-2'} />
          <QuickAudioGenerationPopupButton modelName={'hf:kokoro'} />
        </div>
      </div>
    </Layout>
  )
}

export default DeveloperPage