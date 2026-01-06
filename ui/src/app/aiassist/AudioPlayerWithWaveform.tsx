import React, { useRef } from 'react'
import WaveSurfer from 'wavesurfer.js'

export function AudioPlayerWithWaveform({ audioBlob }) {
  const waveformRef = useRef<any>(null)
  const wavesurferRef = useRef<WaveSurfer>(null)

  React.useEffect(() => {
    wavesurferRef.current = WaveSurfer.create({
      container: waveformRef.current,
      waveColor: 'violet',
      progressColor: 'purple',
    })

    if (audioBlob) {
      wavesurferRef.current.loadBlob(audioBlob)
    }

    return () => {
      if (wavesurferRef.current) {
        wavesurferRef.current.destroy()
      }
    }
  }, [audioBlob])

  // const wavesurfer = useWaveSurfer(waveformRef, {});
  //
  // React.useEffect(() => {
  //   if (!wavesurfer) return
  //
  //   if (audioBlob) {
  //     wavesurfer.loadBlob(audioBlob);
  //   }
  //
  //   return () => {
  //     wavesurfer.destroy()
  //   }
  // }, [audioBlob])

  return (
    <div>
      <div id='waveform' ref={waveformRef}></div>
      {audioBlob && (
        <audio controls>
          <source src={URL.createObjectURL(audioBlob)} type='audio/wav' />
        </audio>
      )}
    </div>
  )
}
