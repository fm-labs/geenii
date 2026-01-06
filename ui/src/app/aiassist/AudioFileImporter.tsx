import { useCallback } from 'react'

export interface AudioFileImporterProps {
  onData?: (blob: Blob) => void
  localStorageKey?: string // @todo: Move localstorage feature outside of this component
}

export function AudioFileImporter({ onData, localStorageKey }: AudioFileImporterProps) {
  const handleFileChange = useCallback(
    (event) => {
      const file = event.target.files[0]
      console.log('File selected:', file)
      if (file && (file.type === 'audio/wav' || file.type === 'audio/x-wav')) {
        const reader = new FileReader()
        reader.onloadend = () => {
          try {
            if (reader.error) {
              throw reader.error
            }
            if (reader.result === null) {
              throw new Error('Empty file received.')
            }
            if (!(reader.result instanceof ArrayBuffer)) {
              throw new Error('Unexpected chunk type received.')
            }

            // Convert ArrayBuffer to Blob
            const blob = new Blob([new Uint8Array(reader.result)], { type: 'audio/wav' })

            // Save Blob object as a data URL in local storage
            if (localStorageKey) {
              localStorage.setItem(localStorageKey, URL.createObjectURL(blob))
            }

            // Call parent component callback
            if (onData) {
              onData(blob)
            }

            console.log(
              `Audio file has been imported.${
                localStorageKey ? ` (Saved in local storage: ${localStorageKey})` : ''
              }`,
            )
          } catch (error) {
            console.error('Error reading file:', error)
          }
        }
        reader.readAsArrayBuffer(file)
      } else {
        console.error('Please upload a valid WAV file.')
      }
    },
    [localStorageKey, onData],
  )

  return (
    <div>
      <input type='file' accept='.wav' onChange={handleFileChange} />
    </div>
  )
}
