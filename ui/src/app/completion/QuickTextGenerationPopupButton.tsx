import React from 'react'
import Popup from '../../ui/Popup.tsx'
import QuickCompletion from './QuickCompletion.tsx'
import { AppContext } from '../../context/AppContext.tsx'
import Button from '../../ui/Button.tsx'
import useNotification from '../../hooks/useNotification.ts'

const QuickTextGenerationPopupButton = ({ modelName }) => {
  const [isOpen, setIsOpen] = React.useState(false)
  const [completion, setCompletion] = React.useState('')
  const [isThinking, setIsThinking] = React.useState(false)
  const notify = useNotification()
  const context = React.useContext(AppContext)
  if (!context) {
    throw new Error('AppContext is not provided')
  }

  const handleCompletion = async (prompt: string) => {
    console.log('>> SUBMIT INPUT', prompt)
    setCompletion('')
    if (prompt.trim()==='') {
      console.warn('>> EMPTY INPUT, NOT SUBMITTING')
      return // do not submit empty input
    }

    setIsThinking(true)
    const response = await context.xaiApi.generateCompletion({ model: modelName, prompt })
      .catch((err) => {
        console.error('Error generating completion:', err)
        notify.error('Error generating completion: ' + err.message)
      })
      .finally(() => {
        setIsThinking(false)
      })
    console.log('>> XAI RESPONSE', response)
    if (!response || !response.output || response.output.length === 0) {
      console.warn('>> NO OUTPUT FROM XAI RESPONSE')
      return
    }
    setCompletion(response?.output[0]?.content[0]?.text)
  }

  return (
    <>
      <Button
        onClick={() => setIsOpen(true)}
      >Quick Text Generation
      </Button> {isThinking ? 'Thinking...':''}

      {/* Popup for Quick Completion */}
      <Popup show={isOpen} onClose={() => setIsOpen(false)} title="Quick Completion" size="md"
             showCloseButton={true}>
        <div>
          <h2 className="text-xl font-semibold mb-4">Quick Text Generation</h2>
          <p className="text-gray-600 mb-4">
            Quickly generate text completions using the input below. This feature is designed for rapid
            prototyping and testing.
          </p>
          <QuickCompletion defaultPrompt={'Tell a joke about AI'} onSubmit={handleCompletion} />
        </div>

        <div className="mt-8">
          <h3 className="text-lg font-semibold mb-2">Generated Completion</h3>
          <p className="text-gray-700">{completion || 'No completion generated yet.'}</p>
        </div>
      </Popup>
    </>
  )
}

export default QuickTextGenerationPopupButton
