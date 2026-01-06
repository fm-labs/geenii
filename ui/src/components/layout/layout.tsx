import React, { PropsWithChildren } from 'react'
import {
  BotIcon,
  SlidersHorizontalIcon,
} from 'lucide-react'
import {
  APP_NAME,
  FEATURE_AGENTS_ENABLED,
  FEATURE_CHAT_ENABLED,
  FEATURE_FLOWS_ENABLED,
  FEATURE_MCP_ENABLED,
} from '@/constants.ts'


const Layout = (props: PropsWithChildren) => {

  const navItemStyle = "text-sm text-gray-400 hover:bg-blue-50 px-3 py-2 rounded"

  return (
    <div>
      <header className={"absolute top-0 left-0 w-full _bg-white border-b border-gray-200 shadow-md z-10"}>
        <div className={"flex flex-row w-full justify-between items-center px-10"}>
          <div className={"flex flex-row"}>
            <BotIcon />
            <span className="ml-2 font-bold text-lg">
              <a href="#/welcome">{APP_NAME}</a>
            </span>
          </div>
          <div>
            <ul className="space-x-3 p-4 flex items-center justify-center">
              {/*<li className="text-sm text-gray-600 hover:bg-blue-50 px-1"><a href="#/welcome">Start</a></li>*/}
              {FEATURE_CHAT_ENABLED && <li className={navItemStyle}><a href="#/chat">Chat</a></li>}
              {FEATURE_AGENTS_ENABLED && <li className={navItemStyle}><a href="#/agents">Agents</a></li>}
              {FEATURE_MCP_ENABLED && <li className={navItemStyle}><a href="#/mcp">MCP</a></li>}
              {FEATURE_FLOWS_ENABLED && <li className={navItemStyle}><a href="#/flows">Flows</a></li>}
            </ul>
          </div>
          <div className={"flex flex-row"}>
            {/*<SettingsIcon />*/}
            <a href="#/settings"><SlidersHorizontalIcon /></a>
            {/*<UserIcon />*/}
          </div>
        </div>
      </header>

      <div className="content _ml-64 mt-10">
        <div className="flex flex-col justify-center min-h-screen p-4">
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
