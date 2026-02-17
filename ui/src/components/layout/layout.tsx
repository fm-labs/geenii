import React, { PropsWithChildren } from 'react'
import {
  BotIcon,
  SlidersHorizontalIcon,
} from 'lucide-react'
import {
  APP_NAME,
  FEATURE_AGENTS_ENABLED,
  FEATURE_CHAT_ENABLED, FEATURE_COMPLETION_ENABLED,
  FEATURE_FLOWS_ENABLED,
  FEATURE_MCP_ENABLED, FEATURE_SETTINGS_ENABLED, FEATURE_TOOLS_ENABLED,
} from '@/constants.ts'

const SHOW_NAV_MENU = true

const Layout = (props: PropsWithChildren) => {

  const navItemStyle = "text-sm text-gray-400 hover:bg-blue-50 px-3 py-2 rounded"

  return (
    <div>
      <header className={"fixed top-0 left-0 w-full border-b shadow-md z-10000 p-2"}>
        <div className={"flex flex-row w-full justify-between items-center max-w-7xl px-4 mx-auto"}>
          <div className={"flex flex-row"}>
            <BotIcon />
            <span className="ml-2 font-bold text-lg">
              <a href="#/">{APP_NAME}</a>
            </span>
          </div>
          <div>
            {SHOW_NAV_MENU && <ul className="space-x-3 flex items-center justify-center">
              {/*<li className="text-sm text-gray-600 hover:bg-blue-50 px-1"><a href="#/welcome">Start</a></li>*/}
              {FEATURE_COMPLETION_ENABLED && <li className={navItemStyle}><a href="#/completions">Completions</a></li>}
              {FEATURE_CHAT_ENABLED && <li className={navItemStyle}><a href="#/chat">Chat</a></li>}
              {FEATURE_AGENTS_ENABLED && <li className={navItemStyle}><a href="#/assistants">Assistants</a></li>}
              {FEATURE_TOOLS_ENABLED && <li className={navItemStyle}><a href="#/tools">Tools</a></li>}
              {FEATURE_MCP_ENABLED && <li className={navItemStyle}><a href="#/mcp">MCP</a></li>}
              {FEATURE_FLOWS_ENABLED && <li className={navItemStyle}><a href="#/flows">Flows</a></li>}
            </ul>}
          </div>
          <div className={"flex flex-row"}>
            {/*<SettingsIcon />*/}
            {FEATURE_SETTINGS_ENABLED && <a href="#/settings"><SlidersHorizontalIcon /></a>}
            {/*<UserIcon />*/}
          </div>
        </div>
      </header>

      <div className="content max-w-7xl mx-auto pt-12">
        <div className="flex flex-col justify-center min-h-screen">
          <div className="flex flex-col justify-center mb-4">
            <div className={'grow'}>
              {props.children}
            </div>
          </div>
        </div>
      </div>

      {/*Main content*/}

      {/*Footer*/}
      {/*<footer className="bg-gray-50 text-center py-2">
        <p className="text-sm">
         g33nii is still an early alpha version.
          Please report any issues on the <a href="https://github.com/fm-labs/g33nii-desktop" target="_blank" className="text-blue-600 hover:underline">GitHub repository</a>.
        </p>
      </footer>*/}
    </div>
  )

}

export default Layout
