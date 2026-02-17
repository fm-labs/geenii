import React from 'react'
import Layout from '../../components/layout/layout.tsx'
import TypewriterText from '../../ui/TypewriterText.tsx'
import { Button } from '../../ui'
import { useNavigate } from '../../app-router.tsx'
import Header from '@/components/header.tsx'
import QuickTextGenerationPopupButton from '@/app/completion/components/QuickTextGenerationPopupButton.tsx'
import QuickImageGenerationPopupButton from '@/app/completion/components/QuickImageGenerationPopupButton.tsx'
import QuickAudioGenerationPopupButton from '@/app/completion/components/QuickAudioGenerationPopupButton.tsx'
import { AppContext } from '@/context/AppContext.tsx'
import TauriUpdaterPanelItem from '@/components/tauri/TauriUpdaterPanelItem.tsx'
import "@/Animate.scss"

const greetings = [
  // "Hello! 👋",
  // "Hi there! 😊",
  // "Greetings! 🙌",
  // "Welcome! 🎉",
  // "Hi",
  // "Hello",
  // "Welcome back",
  // "Howdy",
  // "Greetings",
  // "Salutations",
  // "Good to see you",
  // "Hey there",
  // "Nice to see you",
  // "Good day",
  // "Hola",
  // "Bonjour",
  "h1, 1'm g33n11"
]

const messages = [
  // "What would you like to do today?",
  // "Ready to start a new conversation?",
  // "How can I assist you today?",
  // "Let's get started!",
]

const agentSelfIntro = [
  //"1 am still under development, but 1 will be ready s00n :)",
]

const getRandomElement = (arr: string[]) => {
  return arr[Math.floor(Math.random() * arr.length)]
}

const SelfIntro = () => {
  const [introIdx, setIntroIdx] = React.useState<number>(0)

  React.useEffect(() => {
    const interval = setInterval(() => {
      setIntroIdx((prevIdx) => (prevIdx + 1) % agentSelfIntro.length)
    }, 8000) // Change message every 8 seconds

    return () => clearInterval(interval)
  }, [])

  return (
    <h2 className="text-lg font-medium">
      <TypewriterText text={agentSelfIntro[introIdx]} delay={0} showCursor={false} />
    </h2>
  )
}

const WelcomeScreen = () => {
  const navigate = useNavigate()
  const { isTauri } = React.useContext(AppContext)

  const greeting = getRandomElement(greetings)

  return (
    <div className="flex flex-col justify-center min-h-screen">
      <div className="flex flex-col justify-center mb-4">
        <div className={'grow'}>

          <div className={"text-center"}>
            <div className={"relative my-6"}>
              <img src={'/bot_white.svg'} alt="logo" className={"inline-block w-1/3 max-w-3xl pulse rotate-burst"} />
            </div>
          </div>

          <div className="text-center mb-4">
            <h1 className="text-2xl font-bold"><TypewriterText text={greeting} delay={500} showCursor={false} /></h1>
          </div>
          {/*<div className="text-center mb-4">
            <h2 className="text-xl font-bold"><TypewriterText text={getRandomElement(messages)} delay={2000} showCursor={false} /></h2>
          </div>*/}
          {/*<div className="text-center mb-4 max-w-xl mx-auto">
            <SelfIntro />
          </div>*/}

          {/*<div className={"max-w-1/2 mx-auto p-4 text-center"}>
            <div className="flex flex-col gap-4 justify-center mt-8">
              <div className="text-center mb-4">
                <Button onClick={() => navigate('/chat')}>Start new chat</Button>
              </div>
            </div>
          </div>*/}

          <div className={"max-w-1/2 mx-auto p-4 text-center"}>
            <div className="flex flex-col gap-1 justify-center mt-8">
              <p className={"text-muted-foreground"}>currently incubating. stay tuned. check for updates.</p>
            </div>
          </div>
        </div>
      </div>

    </div>
  )
}

export default WelcomeScreen
