import React, { ChangeEventHandler, KeyboardEventHandler } from 'react'
import { Button } from '@/components/ui/button'
import { ArrowLeft, ImagePlus, MoreVertical, Paperclip, Phone, Plus, Send, Video } from 'lucide-react'

interface AgentChatInputFormProps {
  onChange?: (data: any) => void,
  onSubmit?: (data: any) => Promise<void>
}

const AgentChatInputForm = (props: AgentChatInputFormProps) => {
  const [input, setInput] = React.useState<string>('')

  const handleInputChange: ChangeEventHandler<HTMLTextAreaElement|HTMLInputElement> = (e) => {
    const target = e.target as HTMLTextAreaElement
    setInput(target.value)

    // get content height and set textarea height
    target.style.height = 'auto' // reset height
    target.style.height = `${target.scrollHeight}px` // set new height
    // console.log(">> TEXTAREA HEIGHT", target.scrollHeight, target.style.height)
    // console.log(">> TEXTAREA VALUE", target.value)
    // console.log(">> TEXTAREA", target)

    if (props?.onChange) {
      props.onChange(target.value)
    }
  }

  const handleSubmit = () => {
    console.log("Submitting input:", input)
    if (props?.onSubmit) {
      props.onSubmit(input).then(() => {
        setInput('')
      })
    } else {
      console.warn("No onSubmit handler provided")
    }
  }

  const handleInputKeyDown: KeyboardEventHandler<HTMLTextAreaElement|HTMLInputElement> = (e) => {
    if (e.key.toLowerCase()==='enter' && e.shiftKey===false) {
      e.preventDefault()
      e.stopPropagation()
      handleSubmit()
    }
  }

  return (
    <>
      <form className="flex w-full flex-none gap-2">
        <div
          className="border-input bg-card focus-within:ring-ring flex flex-1 items-center gap-2 rounded-md border px-2 py-1 focus-within:ring-1 focus-within:outline-hidden lg:gap-4">

          <label className="flex-1">
            <span className="sr-only">Chat Text Box</span>
            <input
              type="text"
              placeholder="Type your messages..."
              className="h-8 w-full bg-inherit focus-visible:outline-hidden"
              value={input}
              onKeyDown={handleInputKeyDown}
              onChange={handleInputChange}
            />
          </label>
          <div className="space-x-1">
            <Button
              size="icon"
              type="button"
              variant="ghost"
              className="h-8 rounded-md"
            >
              <Plus size={20} className="stroke-muted-foreground" />
            </Button>
            <Button
              size="icon"
              type="button"
              variant="ghost"
              className="hidden h-8 rounded-md lg:inline-flex"
            >
              <ImagePlus
                size={20}
                className="stroke-muted-foreground"
              />
            </Button>
            <Button
              size="icon"
              type="button"
              variant="ghost"
              className="hidden h-8 rounded-md lg:inline-flex"
            >
              <Paperclip
                size={20}
                className="stroke-muted-foreground"
              />
            </Button>
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="hidden sm:inline-flex"
            onClick={handleSubmit}
          >
            <Send size={20} />
          </Button>
        </div>
        {/*<Button className="h-full sm:hidden" onClick={handleSubmit}>*/}
        {/*  <Send size={18} /> Send*/}
        {/*</Button>*/}
      </form>
    </>
  )
}

export default AgentChatInputForm