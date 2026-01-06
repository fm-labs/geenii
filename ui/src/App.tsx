import React from 'react'
import { Bounce, ToastContainer } from 'react-toastify'
import { AppContextProvider } from './context/AppContextProvider.tsx'
import ServerContextProvider from './context/ServerContextProvider.tsx'
import AppRouter from './app-router.tsx'
import './tailwind.css'
import './App.scss'
import { ThemeProvider } from '@/components/theme-provider.tsx'
import AppSocket from '@/app-socket.tsx'

const App = () => {

  return (
    <>
      <ThemeProvider defaultTheme="dark" storageKey="vite-ui-theme">
        <ServerContextProvider>
          <AppContextProvider>
            <AppRouter />
            {/*<AppSocket />*/}
            {/*<AiAssistPanel />*/}
          </AppContextProvider>
        </ServerContextProvider>
        <ToastContainer
          position="top-right"
          autoClose={5000}
          hideProgressBar={false}
          newestOnTop={false}
          closeOnClick={false}
          rtl={false}
          pauseOnFocusLoss
          draggable
          pauseOnHover
          theme="light"
          transition={Bounce}
        />
      </ThemeProvider>
    </>
  )
}

export default App
