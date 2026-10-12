import React, { PropsWithChildren } from 'react'
import {
  BotIcon,
} from 'lucide-react'
import {
  FEATURE_AGENTS_ENABLED, FEATURE_APPS_ENABLED,
  FEATURE_CHAT_ENABLED,
  FEATURE_COMPLETION_ENABLED,
  FEATURE_FLOWS_ENABLED,
  FEATURE_MESSAGE_INBOX_ENABLED,
  FEATURE_SETTINGS_ENABLED, FEATURE_TAURI_TITLEBAR_ENABLED,
} from '@/constants.ts'
import MessageInbox from '@/components/layout/message-inbox.tsx'

const SHOW_NAV_MENU = true

const Layout = (props: PropsWithChildren) => {

  const navItemStyle = "text-sm text-gray-400 hover:bg-blue-50 px-3 py-2 rounded"

  return (
    <div>
      <header className={`fixed top-0 left-0 w-full border-b shadow-md z-1000 p-2 bg-black ${FEATURE_TAURI_TITLEBAR_ENABLED ? 'pt-8' : ''}`}>
        <div className={"flex flex-row w-full justify-between items-center _max-w-7xl px-4 mx-auto"}>
          <div className={"flex flex-row"}>
            <a href="#/"><BotIcon color={'#FFF'} /></a>
            {/*<span className="ml-2 font-bold text-lg">
              <a href="#/">{APP_NAME}</a>
            </span>*/}
          </div>
          <div>
            {SHOW_NAV_MENU && <ul className="space-x-3 flex items-center justify-center">
              {/*<li className="text-sm text-gray-600 hover:bg-blue-50 px-1"><a href="#/welcome">Start</a></li>*/}
              {FEATURE_COMPLETION_ENABLED && <li className={navItemStyle}><a href="#/completions">Completions</a></li>}
              {FEATURE_CHAT_ENABLED && <li className={navItemStyle}><a href="#/chat">Chat</a></li>}
              {FEATURE_AGENTS_ENABLED && <li className={navItemStyle}><a href="#/agents">Agents</a></li>}
              {/*FEATURE_TOOLS_ENABLED && <li className={navItemStyle}><a href="#/tools">Tools</a></li>*/}
              {/*FEATURE_MCP_ENABLED && <li className={navItemStyle}><a href="#/mcp">MCP</a></li>*/}
              {FEATURE_APPS_ENABLED && <li className={navItemStyle}><a href="#/apps">Apps</a></li>}
              {FEATURE_FLOWS_ENABLED && <li className={navItemStyle}><a href="#/flows">Flows</a></li>}
              {FEATURE_SETTINGS_ENABLED && <li className={navItemStyle}><a href="#/settings">Settings</a></li>}
            </ul>}
          </div>
          <div className={"flex flex-row"}>
            {/*<SettingsIcon />*/}
            {/*<UserIcon />*/}
            {FEATURE_MESSAGE_INBOX_ENABLED && <MessageInbox pollInterval={30_000} />}
          </div>
        </div>
      </header>

      <div>
        {props.children}
      </div>
    </div>
  )
}

export default Layout
