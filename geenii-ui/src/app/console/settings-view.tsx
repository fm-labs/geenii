import * as React from 'react'

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

import { SettingsFormView } from '@/app/console/components/settings-form-view.tsx'
import { settingsForms } from '@/app/console/settings-forms.ts'
import Header from '@/components/header.tsx'
import AudioSettings from '@/app/console/components/audio-settings.tsx'
import { data } from '@/app/console/settings-navdata.tsx'


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
  const [activeTab, setActiveTab] = React.useState("Profile");

  const activeTabElement = React.useMemo(() => {
    switch (activeTab) {
      case "Appearance":
        return <SettingsFormView schema={settingsForms["appearance"][0]} uiSchema={settingsForms["appearance"][1]} />;
      case "Profile":
        return <SettingsFormView schema={settingsForms["profile"][0]} uiSchema={settingsForms["profile"][1]} />;
      // case "Default Models":
      //   if (!FEATURE_AI_ENABLED) {
      //     return <DisabledFeatureSettingsView />;
      //   }
      //   return <SettingsFormView schema={settingsForms["default_models"][0]} uiSchema={settingsForms["default_models"][1]} />;
      // case "MCP":
      //   if (!FEATURE_MCP_ENABLED) {
      //     return <DisabledFeatureSettingsView />;
      //   }
      //   return <McpServersSettingsView />;
      // case "Models":
      //   if (!FEATURE_AI_ENABLED) {
      //     return <DisabledFeatureSettingsView />;
      //   }
      //   return <AiModelSettingsView />;
      // case "Tools":
      //   if (!FEATURE_TOOLS_ENABLED) {
      //     return <DisabledFeatureSettingsView />;
      //   }
      //   return <ToolsView />
      // case "Apps":
      //   if (!FEATURE_APPS_ENABLED) {
      //     return <DisabledFeatureSettingsView />;
      //   }
      //   return <AppsSettings />
      // case "System Info":
      //   return <SystemInfoView />
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
