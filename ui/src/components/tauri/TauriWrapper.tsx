import React, { PropsWithChildren } from 'react'
import TauriPanel from './TauriPanel.tsx'
import { TauriPanelProvider } from '@/components/tauri/TauriPanelContext.tsx'
import { getCurrentWindow } from '@tauri-apps/api/window';

// when using `"withGlobalTauri": true`, you may use
// const { getCurrentWindow } = window.__TAURI__.window;

const appWindow = getCurrentWindow();


const TauriTitleBar = () => {

  React.useEffect(() => {
    document
      .getElementById('titlebar-minimize')
      ?.addEventListener('click', () => appWindow.minimize());
    document
      .getElementById('titlebar-maximize')
      ?.addEventListener('click', () => appWindow.toggleMaximize());
    document
      .getElementById('titlebar-close')
      ?.addEventListener('click', () => appWindow.close());

    return () => {
      document
        .getElementById('titlebar-minimize')
        ?.removeEventListener('click', () => appWindow.minimize());
      document
        .getElementById('titlebar-maximize')
        ?.removeEventListener('click', () => appWindow.toggleMaximize());
      document
        .getElementById('titlebar-close')
        ?.removeEventListener('click', () => appWindow.close());
    }
  }, [])

  return (
    <div className="titlebar">
      <div data-tauri-drag-region></div>
      <div className="controls">
        <button id="titlebar-minimize" title="minimize">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="24"
            height="24"
            viewBox="0 0 24 24"
          >
            <path fill="currentColor" d="M19 13H5v-2h14z" />
          </svg>
        </button>
        <button id="titlebar-maximize" title="maximize">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="24"
            height="24"
            viewBox="0 0 24 24"
          >
            <path fill="currentColor" d="M4 4h16v16H4zm2 4v10h12V8z" />
          </svg>
        </button>
        <button id="titlebar-close" title="close">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="24"
            height="24"
            viewBox="0 0 24 24"
          >
            <path
              fill="currentColor"
              d="M13.46 12L19 17.54V19h-1.46L12 13.46L6.46 19H5v-1.46L10.54 12L5 6.46V5h1.46L12 10.54L17.54 5H19v1.46z"
            />
          </svg>
        </button>
      </div>
    </div>
  )
}


const TauriWrapper = (props: PropsWithChildren) => {
  return (
    <div className={'TauriWrapper'}>
      <TauriTitleBar />
      {props.children}
      <TauriPanel />
    </div>
  )
}

export default TauriWrapper