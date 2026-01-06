import React from 'react'
import Popup from '../../ui/Popup.tsx'
import QuickCompletion from './QuickCompletion.tsx'
import { AppContext } from '../../context/AppContext.tsx'
import { Button } from '../../ui'
import useNotification from '../../hooks/useNotification.ts'

const QuickImageGenerationPopupButton = ({ modelName }) => {
  const [isOpen, setIsOpen] = React.useState(false)
  const [imageUrl, setImageUrl] = React.useState('')
  const [isThinking, setIsThinking] = React.useState(false)
  const notify = useNotification()
  const context = React.useContext(AppContext)
  if (!context) {
    throw new Error('AppContext is not provided')
  }

  const handleSubmit = async (prompt: string) => {
    console.log('>> SUBMIT INPUT', prompt)
    setImageUrl('')
    if (prompt.trim()==='') {
      console.warn('>> EMPTY INPUT, NOT SUBMITTING')
      return // do not submit empty input
    }

    setIsThinking(true)
    const response = await context.xaiApi.generateImage({ model: modelName, prompt })
      .catch((err) => {
        console.error('Error generating image:', err)
        notify.error('Error generating image: ' + err.message)
      })
      .finally(() => {
        setIsThinking(false)
      })
    if (!response || !response.output || response.output.length===0) {
      console.warn('>> NO OUTPUT FROM XAI RESPONSE')
      return
    }
    console.log('>> XAI RESPONSE', response)

    const output = response?.output[0]
    let imageUrl
    if (output?.url) {
      imageUrl = output.url
    } else if (output?.base64) {
      // Convert base64 to data URL
      imageUrl = `data:image/png;base64,${output.base64}`
    }
    setImageUrl(imageUrl)
  }

  const handleClose = () => {
    setIsOpen(false)
    setImageUrl('')
    setIsThinking(false)
  }

  return (
    <>
      <Button
        onClick={() => setIsOpen(true)}
      >Quick Image Generation
      </Button>

      {/* Popup for Quick Completion */}
      <Popup show={isOpen} onClose={handleClose} title="Quick Completion" size="md"
             showCloseButton={true}>
        <div>
          <h2 className="text-xl font-semibold mb-4">Quick Image Generation</h2>
          <p className="text-gray-600 mb-4">
            Quickly generate an image from a text prompt using the input below.
            This feature is designed with simplicity in mind and easy access.
          </p>
          <QuickCompletion defaultPrompt={'A funky cat riding a unicorn'} onSubmit={handleSubmit} />
        </div>

        <div className="mt-8">
          {isThinking && (
            <p className="text-gray-500 mb-4">Generating image...</p>
          )}
          {imageUrl && (
            <div className="mb-4">
              <img
                src={imageUrl}
                alt="Generated"
                className="w-full h-auto rounded-lg shadow-md"
              />
              <button className="mt-2 text-blue-500 hover:underline"
                onClick={() => {
                  const link = document.createElement('a')
                  link.href = imageUrl
                  link.download = 'generated-image.png'
                  document.body.appendChild(link)
                  link.click()
                  document.body.removeChild(link)
                }}
              >
                Download Image
              </button>
            </div>
          )}
          <p className="text-gray-700 h-16 overflow-y-scroll">{imageUrl || ''}</p>
        </div>
      </Popup>
    </>
  )
}

export default QuickImageGenerationPopupButton
