import { useState } from 'react'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible.tsx'
import { ScrollArea } from '@/components/ui/scroll-area.tsx'
import { Badge } from '@/components/ui/badge.tsx'
import { Card } from '@/components/ui/card.tsx'
import { UserInteractionContent } from '@/app/geechat/geechat-types.ts'
import { Button } from '@/components/ui/button.tsx'
import { XAI_API_URL } from '@/constants.ts'

function syntaxHighlight(json) {
  const str = JSON.stringify(json, null, 2)
  return str.replace(
    /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)/g,
    (match) => {
      if (/^"/.test(match)) {
        if (/:$/.test(match)) return `<span style="color:#7dd3fc">${match}</span>`
        return `<span style="color:#86efac">${match}</span>`
      }
      if (/true|false/.test(match)) return `<span style="color:#c084fc">${match}</span>`
      if (/null/.test(match)) return `<span style="color:#f87171">${match}</span>`
      return `<span style="color:#fde68a">${match}</span>`
    },
  )
}

function RichCard({ children, className = '' }) {
  return (
    <Card className={`max-w-md w-full border bg-card shadow-none rounded-lg gap-2 py-0 ${className}`}>
      {children}
    </Card>
  )
}

function TextBubble({ part, isUser }) {
  return (
    <p className={`text-sm leading-relaxed px-3.5 py-2 rounded-xl max-w-prose ${
      isUser
        ? 'bg-primary text-primary-foreground'
        : 'bg-muted text-foreground'
    }`}>
      {part.text}
    </p>
  )
}

function ImageCard({ part }) {
  return (
    <RichCard>
      <img
        src={part.url}
        alt={part.alt || 'Image'}
        className="w-full max-h-52 object-cover rounded-t-lg"
        //onError={(e) => { e.target.src = "https://images.unsplash.com/photo-1518791841217-8f162f1912da?w=400&q=60" }}
      />
      {part.alt && (
        <div className="px-3 py-1.5">
          <p className="text-xs text-muted-foreground">{part.alt}</p>
        </div>
      )}
    </RichCard>
  )
}

function ToolCallCard({ part }) {
  return (
    <RichCard>
      {/* slim header */}
      <div className="flex items-center gap-2 px-3 py-2 border-b">
        <span className="text-muted-foreground text-xs">⚙</span>
        <span className="font-mono text-xs text-foreground flex-1 truncate">{part.name}()</span>
        {part.call_id && (
          <span className="font-mono text-[10px] text-muted-foreground">{part.call_id}</span>
        )}
      </div>
      {part.arguments && Object.keys(part.arguments).length > 0 && (
        <div className="p-2">
          <pre
            className="bg-muted text-left rounded px-2.5 py-2 font-mono text-[11px] text-foreground leading-relaxed whitespace-pre-wrap break-all">
            {JSON.stringify(part.arguments, null, 2)}
          </pre>
        </div>
      )}
    </RichCard>
  )
}

function ToolCallResultCard({ part }) {
  const isError = !!part.error

  return (
    <RichCard>
      {/* slim header */}
      <div className="flex items-center gap-2 px-3 py-2 border-b">
        <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${isError ? 'bg-destructive' : 'bg-foreground/30'}`} />
        <span className="font-mono text-xs text-foreground flex-1 truncate">{part.name}</span>
        <Badge variant="outline" className="text-[10px] font-mono h-4 px-1.5 text-muted-foreground">
          {isError ? 'error' : 'result'}
        </Badge>
      </div>
      <div className="px-3 py-2">
        {isError ? (
          <p className="text-xs text-destructive font-mono leading-relaxed">{part.error}</p>
        ) : part.result && typeof part.result === 'object' && !Array.isArray(part.result) ? (
          <div className="flex flex-col gap-1">
            {Object.entries(part.result).map(([k, v]) => (
              <div key={k} className="flex items-baseline gap-2 font-mono text-[11px]">
                <span className="text-muted-foreground w-24 flex-shrink-0">{k}</span>
                <span className="text-foreground">{typeof v === 'object' ? JSON.stringify(v) : String(v)}</span>
              </div>
            ))}
          </div>
        ) : (
          <span className="font-mono text-xs text-foreground">{JSON.stringify(part.result)}</span>
        )}
      </div>
    </RichCard>
  )
}

function UserInteractionCard({ part }: { part: UserInteractionContent }) {
  const handleUserChoice = (choice) => {
    console.log('User selected choice:', choice)

    const sendUserChoice = async () => {
      try {
        const response = await fetch(XAI_API_URL + 'api/v1/agents/callback', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            interaction_id: part.interaction_id,
            interaction_type: part.interaction_type,
            choice,
          }),
        })
        if (!response.ok) {
          throw new Error(`Server responded with ${response.status}`)
        }
        console.log('User choice sent successfully')
      } catch (error) {
        console.error('Error sending user choice:', error)
      }
    }

    sendUserChoice().then(() => {
      console.log('User choice processing complete')
    }).catch((error) => {
      console.error('Error in user choice processing:', error)
    })
  }

  return (
    <RichCard>
      <div className="flex items-center gap-2 px-3 py-2 border-b">
        <span className="text-muted-foreground text-xs">👤</span>
        <span className="font-mono text-xs text-foreground flex-1 truncate">{part.interaction_type}</span>
      </div>
      <div className={'flex items-center gap-2 p-2'}>
        {part.choices.map((choice => (
          <div key={choice} className="">
            <Button className="text-sm" onClick={() => handleUserChoice(choice)}>{choice}</Button>
          </div>
        )))}
      </div>
    </RichCard>
  )
}

function JsonCard({ part }) {
  const [open, setOpen] = useState(true)

  return (
    <RichCard>
      <Collapsible open={open} onOpenChange={setOpen}>
        {/* slim header */}
        <CollapsibleTrigger className="w-full">
          <div className="flex items-center gap-2 px-3 py-2 border-b hover:bg-muted/40 transition-colors">
            <span className="font-mono text-[10px] text-muted-foreground">{'{}'}</span>
            <span className="font-mono text-xs text-foreground flex-1 text-left">JSON</span>
            <span className="text-[10px] text-muted-foreground">{open ? '▾' : '▸'}</span>
          </div>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <div className="px-3 py-2">
            <ScrollArea className="max-h-48 overflow-hidden">
              <pre className="font-mono text-left text-[11px] text-foreground leading-relaxed whitespace-pre-wrap break-all max-h-[400px] overflow-y-scroll">
                {JSON.stringify(part.data, null, 2)}
              </pre>
            </ScrollArea>
          </div>
        </CollapsibleContent>
      </Collapsible>
    </RichCard>
  )
}

export function ContentPart({ part, isUser }) {
  switch (part.type) {
    case 'text':
      return <TextBubble part={part} isUser={isUser} />
    case 'image':
      return <ImageCard part={part} />
    case 'tool_call':
      return <ToolCallCard part={part} />
    case 'tool_call_result':
      return <ToolCallResultCard part={part} />
    case 'interaction':
      return <UserInteractionCard part={part} />
    case 'json':
      return <JsonCard part={part} />
    default:
      return <p className="text-xs text-muted-foreground italic">[unsupported: {part.type}]</p>
  }
}