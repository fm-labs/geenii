import * as React from 'react'
import {
  AudioWaveformIcon,
  BotIcon,
  BrainIcon,
  HammerIcon, InfoIcon, PackageIcon, PaletteIcon,
  ServerIcon,
  UserIcon,
} from 'lucide-react'

// import {
//   Breadcrumb,
//   BreadcrumbItem,
//   BreadcrumbLink,
//   BreadcrumbList,
//   BreadcrumbPage,
//   BreadcrumbSeparator,
// } from '@/components/ui/breadcrumb'

import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
} from '@/components/ui/sidebar'

import { SettingsFormView } from '@/app/settings/components/settings-form-view.tsx'
import { McpServersSettingsView } from '@/app/settings/components/mcp-servers-settings-view.tsx'
import { AiModelSettingsView } from '@/app/settings/components/ai-model-settings-view.tsx'
import { settingsForms } from '@/app/settings/settings-forms.ts'
import ToolsView from '@/app/tools/tools.view.tsx'
import WizardsSettings from '@/app/settings/components/wizards-settings.tsx'
import AppsSettings from '@/app/settings/components/apps-settings.tsx'
import {
  FEATURE_AI_ENABLED,
  FEATURE_APPS_ENABLED,
  FEATURE_MCP_ENABLED,
  FEATURE_TOOLS_ENABLED,
  FEATURE_AGENTS_ENABLED,
} from '@/constants.ts'
import Header from '@/components/header.tsx'
import SystemInfoView from '@/app/settings/components/system-info-view.tsx'
import AudioSettings from '@/app/settings/components/audio-settings.tsx'


const data = {
  nav: [
    { name: "Profile", icon: UserIcon },
    { name: "Appearance", icon: PaletteIcon },
    //{ name: "Default Models", icon: BrainIcon },
    { name: "Models", icon: BrainIcon },
    { name: "Wizards", icon: BotIcon },
    { name: "Tools", icon: HammerIcon },
    { name: "MCP", icon: ServerIcon },
    { name: "Apps", icon: PackageIcon },
    //{ name: "Notifications", icon: Bell },
    //{ name: "Navigation", icon: Menu },
    //{ name: "Home", icon: Home },
    //{ name: "Appearance", icon: Paintbrush },
    //{ name: "Messages & media", icon: MessageCircle },
    //{ name: "Language & region", icon: Globe },
    //{ name: "Accessibility", icon: Keyboard },
    //{ name: "Mark as read", icon: Check },
    //{ name: "Audio & video", icon: Video },
    { name: "Audio", icon: AudioWaveformIcon },
    //{ name: "Connected accounts", icon: Link },
    //{ name: "Privacy & visibility", icon: Lock },
    //{ name: "Advanced", icon: Settings },
    { name: "System Info", icon: InfoIcon },
  ],
}



const DisabledFeatureSettingsView = () => {
  return <div>
    <div className={"bg-accent border rounded-lg p-4 mb-4 max-w-3xl"}>
      <h2 className={"text-lg font-bold mb-2"}>Feature not available</h2>
      <p className={"text-muted-foreground"}>This feature is not enabled in your current environment.</p>
    </div>
    {Array.from({ length: 2 }).map((_, i) => (
      <div
        key={i}
        className="bg-muted/50 aspect-video max-w-3xl rounded-xl my-4"
      />
    ))}
  </div>
}

const SettingsView = () => {
  const [activeTab, setActiveTab] = React.useState("System Info");

  const activeTabElement = React.useMemo(() => {
    switch (activeTab) {
      case "Appearance":
        return <SettingsFormView schema={settingsForms["appearance"][0]} uiSchema={settingsForms["appearance"][1]} />;
      case "Profile":
        return <SettingsFormView schema={settingsForms["profile"][0]} uiSchema={settingsForms["profile"][1]} />;
      case "Default Models":
        if (!FEATURE_AI_ENABLED) {
          return <DisabledFeatureSettingsView />;
        }
        return <SettingsFormView schema={settingsForms["default_models"][0]} uiSchema={settingsForms["default_models"][1]} />;
      case "MCP":
        if (!FEATURE_MCP_ENABLED) {
          return <DisabledFeatureSettingsView />;
        }
        return <McpServersSettingsView />;
      case "Models":
        if (!FEATURE_AI_ENABLED) {
          return <DisabledFeatureSettingsView />;
        }
        return <AiModelSettingsView />;
      case "Tools":
        if (!FEATURE_TOOLS_ENABLED) {
          return <DisabledFeatureSettingsView />;
        }
        return <ToolsView />
      case "Wizards":
        if (!FEATURE_AGENTS_ENABLED) {
          return <DisabledFeatureSettingsView />;
        }
        return <WizardsSettings />
      case "Apps":
        if (!FEATURE_APPS_ENABLED) {
          return <DisabledFeatureSettingsView />;
        }
        return <AppsSettings />
      case "System Info":
        return <SystemInfoView />
      case "Audio":
        return <AudioSettings />
      default:
        return <DisabledFeatureSettingsView />;
    }
  }, [activeTab]);

    return (
        <div>
          <SidebarProvider className="items-start">
            <Sidebar collapsible="none" className="hidden md:flex bg-transparent">
              <SidebarContent>
                <SidebarGroup>
                  <SidebarGroupContent>
                    <SidebarMenu>
                      {data.nav.map((item) => (
                        <SidebarMenuItem key={item.name}>
                          <SidebarMenuButton
                            asChild
                            isActive={item.name === activeTab}
                          >
                            <a onClick={() => setActiveTab(item.name)}>
                              <item.icon />
                              <span>{item.name}</span>
                            </a>
                          </SidebarMenuButton>
                        </SidebarMenuItem>
                      ))}
                    </SidebarMenu>
                  </SidebarGroupContent>
                </SidebarGroup>
              </SidebarContent>
            </Sidebar>
            <div className="flex flex-1 flex-col">
              {/*<header className="flex h-16 shrink-0 items-center gap-2 transition-[width,height] ease-linear group-has-data-[collapsible=icon]/sidebar-wrapper:h-12">
                <div className="flex items-center gap-2 px-4">
                  <Breadcrumb>
                    <BreadcrumbList>
                      <BreadcrumbItem className="hidden md:block">
                        <BreadcrumbLink href="#/settings">Settings</BreadcrumbLink>
                      </BreadcrumbItem>
                      <BreadcrumbSeparator className="hidden md:block" />
                      <BreadcrumbItem>
                        <BreadcrumbPage>{activeTab}</BreadcrumbPage>
                      </BreadcrumbItem>
                    </BreadcrumbList>
                  </Breadcrumb>
                </div>
              </header>*/}
              <div className="flex flex-1 flex-col gap-4 p-4 pt-0 max-h-1/4">
                <Header title={activeTab} />
                {activeTabElement}
              </div>
            </div>
          </SidebarProvider>
        </div>
    );
};

export default SettingsView;
