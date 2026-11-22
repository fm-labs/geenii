import React from 'react'
import { Bounce, ToastContainer } from 'react-toastify'
import { AppContextProvider } from './context/app-context-provider.tsx'
import ServerContextProvider from './context/server-context-provider.tsx'
import AppRouter from './app-router.tsx'
import { ThemeProvider } from '@/components/theme-provider.tsx'
import { ApiProvider } from '@/context/api-context.tsx'
import AppearanceSettingsSync from '@/components/appearance-settings-sync.tsx'
import './tailwind.css'
import './App.scss'

const WebApp = () => {

  return (
    <>
      <ThemeProvider defaultTheme="system" storageKey="geenii-theme">
        <ServerContextProvider>
          <ApiProvider>
            <AppearanceSettingsSync />
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

export default WebApp
