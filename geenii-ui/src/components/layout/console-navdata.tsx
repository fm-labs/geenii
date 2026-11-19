// This is sample data.
import { BotIcon } from 'lucide-react'

export const consoleNavData = {
  navMain: [
    {
      title: 'Manage',
      url: '#',
      items: [
        {
          title: 'Agents',
          url: '#/console/configure/agents',
          icon: BotIcon
        },
        {
          title: 'Skills',
          url: '#/console/configure/skills',
        },
        {
          title: 'MCP Servers',
          url: '#/console/configure/mcp-servers',
        },
        {
          title: 'Tools',
          url: '#/console/configure/tools',
        },
        {
          title: 'Models',
          url: '#/console/configure/models',
        },
        {
          title: 'Apps',
          url: '#/console/configure/apps',
        },
        // {
        //   title: 'Environments',
        //   url: '#/console/configure/environments',
        // },
        // {
        //   title: 'Memory Stores',
        //   url: '#/console/configure/memory-stores',
        // },
        // {
        //   title: 'Vaults',
        //   url: '#/console/configure/vaults',
        // },
      ],
    },
    {
      title: 'Install from Catalog',
      url: '#',
      items: [
        // {
        //   title: 'Apps',
        //   url: '#/console/catalog/apps',
        // },
        {
          title: 'Ollama Models',
          url: '#/console/catalog/models',
        },
        {
          title: 'Docker MCP Servers',
          url: '#/console/catalog/mcp',
        },
      ],
    },
    {
      title: 'System',
      url: '#',
      items: [
        {
          title: 'Info',
          url: '#/console/system/info',
        },
        {
          title: 'Usage stats',
          url: '#/console/system/stats',
        },
        {
          title: 'Process stats',
          url: '#/console/system/process-stats',
        },
        {
          title: 'Scheduler',
          url: '#/console/system/scheduler',
        },
        {
          title: 'Services',
          url: '#/console/system/services',
        },
        {
          title: 'Processes',
          url: '#/console/system/processes',
        },
        // {
        //   title: 'Plugins',
        //   url: '#/console/system/plugins',
        // },
        {
          title: 'Settings',
          url: '#/console/system/settings',
          //isActive: true,
        },
      ],
    },
    {
      title: 'Playground',
      url: '#',
      items: [
        {
          title: 'Completions Playground',
          url: '#/console/playground/completions',
        },
        {
          title: 'Tools Playground',
          url: '#/console/playground/tools',
        },
        {
          title: 'Chat Playground',
          url: '#/console/playground/xchat',
        },
      ],
    },
  ],
}
