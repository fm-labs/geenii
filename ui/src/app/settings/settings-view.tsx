import * as React from 'react'
import { BotIcon, ServerIcon, Video } from 'lucide-react'

import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from '@/components/ui/breadcrumb'

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
import { RJSFSchema } from '@rjsf/utils'
import { SettingsFormView } from '@/app/settings/components/settings-form-view.tsx'
import { McpServersSettingsView } from '@/app/settings/components/mcp-servers-settings-view.tsx'
import { AiModelSettingsView } from '@/app/settings/components/ai-model-settings-view.tsx'
import { settingsForms } from '@/app/settings/settings-forms.ts'

const data = {
  nav: [
    //{ name: "Profile", icon: UserIcon },
    { name: "Default Assistant", icon: BotIcon },
    { name: "AI Models", icon: BotIcon },
    //{ name: "MCP Servers", icon: ServerIcon },
    //{ name: "Notifications", icon: Bell },
    //{ name: "Navigation", icon: Menu },
    //{ name: "Home", icon: Home },
    //{ name: "Appearance", icon: Paintbrush },
    //{ name: "Messages & media", icon: MessageCircle },
    //{ name: "Language & region", icon: Globe },
    //{ name: "Accessibility", icon: Keyboard },
    //{ name: "Mark as read", icon: Check },
    //{ name: "Audio & video", icon: Video },
    //{ name: "Connected accounts", icon: Link },
    //{ name: "Privacy & visibility", icon: Lock },
    //{ name: "Advanced", icon: Settings },
  ],
}



const DummySettingsView = () => {
  return <div>
    {Array.from({ length: 10 }).map((_, i) => (
      <div
        key={i}
        className="bg-muted/50 aspect-video max-w-3xl rounded-xl my-4"
      />
    ))}
  </div>
}


const SettingsView = () => {
  const [activeTab, setActiveTab] = React.useState("Default Models");

  const activeTabElement = React.useMemo(() => {
    switch (activeTab) {
      case "Profile":
        return <SettingsFormView schema={settingsForms["profile"][0]} uiSchema={settingsForms["profile"][1]} />;
      case "Default Models":
        return <SettingsFormView schema={settingsForms["default_models"][0]} uiSchema={settingsForms["default_models"][1]} />;
      case "Messages & media":
        return <DummySettingsView />;
      case "MCP Servers":
        return <McpServersSettingsView />;
      case "AI Models":
        return <AiModelSettingsView />;
      default:
        return <DummySettingsView />;
    }
  }, [activeTab]);

    return (
        <div>
            {/*<h1 className="text-2xl font-bold mb-4">Settings</h1>*/}
            {/*<p className="text-gray-600 mb-4">*/}
            {/*    App settings allow you to configure various aspects of the application, such as model preferences,*/}
            {/*    API keys, and other options. Adjust these settings to tailor the app to your needs.*/}
            {/*</p>*/}

            {/*<section>*/}
            {/*    <h2 className="text-xl font-semibold mb-2">Model Preferences</h2>*/}
            {/*    <p className="text-gray-600 mb-4">*/}
            {/*        Configure your preferred models for text generation, image generation, and other tasks.*/}
            {/*    </p>*/}
            {/*     Add model preference settings here */}
            {/*</section>*/}

            {/*<section>*/}
            {/*    <h2 className="text-xl font-semibold mb-2">Integrations</h2>*/}
            {/*    <p className="text-gray-600 mb-4">*/}
            {/*        Manage integrations with external services, such as cloud storage or third-party APIs.*/}
            {/*    </p>*/}
            {/*     Add integrations settings here */}
            {/*</section>*/}

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
            <main className="flex flex-1 flex-col _overflow-hidden">
              <header className="flex h-16 shrink-0 items-center gap-2 transition-[width,height] ease-linear group-has-data-[collapsible=icon]/sidebar-wrapper:h-12">
                <div className="flex items-center gap-2 px-4">
                  <Breadcrumb>
                    <BreadcrumbList>
                      <BreadcrumbItem className="hidden md:block">
                        <BreadcrumbLink href="#">Settings</BreadcrumbLink>
                      </BreadcrumbItem>
                      <BreadcrumbSeparator className="hidden md:block" />
                      <BreadcrumbItem>
                        <BreadcrumbPage>{activeTab}</BreadcrumbPage>
                      </BreadcrumbItem>
                    </BreadcrumbList>
                  </Breadcrumb>
                </div>
              </header>
              <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-4 pt-0">
                {activeTabElement}
              </div>
            </main>
          </SidebarProvider>
        </div>
    );
};

export default SettingsView;
