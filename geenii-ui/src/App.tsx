import React from 'react'
import { Bounce, ToastContainer } from 'react-toastify'
import { AppContextProvider } from './context/app-context-provider.tsx'
import ServerContextProvider from './context/server-context-provider.tsx'
import AppRouter from './app-router.tsx'
import { ThemeProvider } from '@/components/theme-provider.tsx'
import { ApiProvider } from '@/context/api-context.tsx'
import './tailwind.css'
import './App.scss'

const App = () => {

  return (
    <>
      <ThemeProvider defaultTheme="system" storageKey="vite-ui-theme">
        <ServerContextProvider>
          <ApiProvider>
            <AppContextProvider>
              <AppRouter />
            </AppContextProvider>
          </ApiProvider>
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
