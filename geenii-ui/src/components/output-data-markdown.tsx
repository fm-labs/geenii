// https://react-syntax-highlighter.github.io/react-syntax-highlighter/demo/prism.html
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import React from 'react'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { a11yDark } from 'react-syntax-highlighter/dist/esm/styles/prism'

const prismStyle = a11yDark
// GitHub-flavored markdown: tables, strikethrough, task lists, autolinks
const remarkPlugins = [remarkGfm]

export const OutputDataMarkdown = ({ data, showCursor }: { data: string, showCursor?: boolean }) => {
  return (
    <Markdown
      remarkPlugins={remarkPlugins}
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
          ) : (
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