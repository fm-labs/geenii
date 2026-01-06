import React, { PropsWithChildren, useEffect, useState } from 'react'
import Markdown from 'react-markdown'

import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { a11yDark } from 'react-syntax-highlighter/dist/esm/styles/prism'

// https://react-syntax-highlighter.github.io/react-syntax-highlighter/demo/prism.html
const prismStyle = a11yDark

const OutputDataMarkdown = ({ data, showCursor }: { data: string, showCursor?: boolean }) => {
  return (
    <Markdown
      components={{
        code({ node, className, children, ...props }) {
          const match = /language-(\w+)/.exec(className || '')
          return match ? (
            <SyntaxHighlighter
              style={prismStyle}
              showLineNumbers={false}
              wrapLines={true}
              language={match[1]}
              PreTag="div"
              {...props}
            >
              {String(children).replace(/\n$/, '')}
            </SyntaxHighlighter>
          ):(
            <code className={className} {...props}>
              {children}
            </code>
          )
        },
      }}
    >
      {data}
    </Markdown>
  )
}

interface TypewriterTextProps extends PropsWithChildren<any> {
  text: string;
  speed?: number; // Speed in milliseconds per character
  delay?: number; // Initial delay before starting the typing effect
  limit?: number; // Maximum duration for the typing effect
  showCursor?: boolean; // Whether to show the cursor
  cursorChar?: string; // Character for the cursor
  className?: string; // Additional CSS classes
  onComplete?: () => void; // Callback when typing is complete
  children?: React.ReactNode; // Children elements
}

const TypewriterText = ({
                          text,
                          speed = 10,
                          delay = 0,
                          limit = 2000,
                          showCursor = true,
                          cursorChar = '|',
                          className = '',
                          onComplete = () => {
                          },
                          children,
                        }: TypewriterTextProps) => {
  const [displayedText, setDisplayedText] = useState('')
  const [currentIndex, setCurrentIndex] = useState(0)
  const [isComplete, setIsComplete] = useState(false)

  useEffect(() => {
    setDisplayedText('')
    setCurrentIndex(0)
    setIsComplete(false)
  }, [text])

  useEffect(() => {
    if (currentIndex < text.length) {
      const calculatedDuration = speed * text.length + delay
      let effectiveSpeed = speed
      if (limit > 0 && calculatedDuration > limit) {
        effectiveSpeed = Math.min(speed, limit / calculatedDuration * speed)
        console.log(`Adjusted Speed: ${effectiveSpeed}ms for text length: ${text.length}`)
      }
      const timer = setTimeout(() => {
        const nextText = text.slice(0, currentIndex + 1)

        setDisplayedText(nextText)
        setCurrentIndex(currentIndex + 1)
      }, currentIndex===0 ? delay:effectiveSpeed)

      return () => clearTimeout(timer)
    } else if (currentIndex===text.length && !isComplete) {
      setIsComplete(true)
      onComplete()
    }
  }, [currentIndex, text, speed, delay, isComplete, onComplete])

  // if (isComplete && children) {
  //   return children
  // }


  return (
    <div className={className}>
      <OutputDataMarkdown data={displayedText + (showCursor && !isComplete ? "_" : "&nbsp;")} />
    </div>
  )
}

export default TypewriterText
