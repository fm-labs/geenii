import React from 'react'

interface ModelThinkingIndicatorProps {
  text?: string;
  show?: boolean;
}

export const ModelThinkingIndicator = (props) => {
  const { text = 'Thinking', show = true } = props as ModelThinkingIndicatorProps
  //const chars = ['', '.', '..', '...'];
  //const chars = ['-', '\\', '|', '/', '-', '\\', '|', '/'];
  const chars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
  const [charIndex, setCharIndex] = React.useState(0)

  React.useEffect(() => {
    const interval = setInterval(() => {
      setCharIndex((prevIndex) => Math.abs((prevIndex + 1) % chars.length))
    }, 100) // Change the interval as needed
    return () => clearInterval(interval) // Cleanup on unmount
  })

  return show ? (<span>{text + ' ' + chars[charIndex]}</span>):null
}
