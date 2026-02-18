import React from "react";
import { useDockerMcpCatalog } from "@/app/mcp-servers/components/docker-mcp-catalog-provider.tsx";
import { Button } from "@/components/ui/button";
import Form from "@rjsf/shadcn";
import validator from "@rjsf/validator-ajv8";
import JsonView from "@/components/json-view.tsx";
import { Separator } from "@/components/ui/separator.tsx";
import {RJSFSchema} from "@rjsf/utils";
import { Input } from '@/components/ui/input.tsx'

/**
 * Render the docker MCP toolkit catalog
 *
 * Example data:
 * "brave": {
 *       "description": "Search the Web for pages, images, news, videos, and more using the Brave Search API.",
 *       "title": "Brave Search",
 *       "type": "server",
 *       "dynamic": {},
 *       "dateAdded": "2025-05-05T20:08:35Z",
 *       "image": "mcp/brave-search@sha256:b903e1ad948114517fa7dc767a9bf4c2d1b9529164bcc0fb9c58b344c56aa335",
 *       "ref": "",
 *       "readme": "http://desktop.docker.com/mcp/catalog/v3/readme/brave.md",
 *       "toolsUrl": "http://desktop.docker.com/mcp/catalog/v3/tools/brave.json",
 *       "source": "https://github.com/brave/brave-search-mcp-server/tree/a25160bcad9cded587b8ed94eacf9688a1b552de",
 *       "upstream": "https://github.com/brave/brave-search-mcp-server",
 *       "remote": {},
 *       "icon": "https://avatars.githubusercontent.com/u/12301619?s=200\u0026v=4",
 *       "tools": [
 *         {
 *           "name": "brave_image_search",
 *           "parameters": {
 *             "type": "",
 *             "properties": null,
 *             "required": null
 *           },
 *           "container": {}
 *         },
 *         {
 *           "name": "brave_local_search",
 *           "parameters": {
 *             "type": "",
 *             "properties": null,
 *             "required": null
 *           },
 *           "container": {}
 *         },
 *         {
 *           "name": "brave_news_search",
 *           "parameters": {
 *             "type": "",
 *             "properties": null,
 *             "required": null
 *           },
 *           "container": {}
 *         },
 *         {
 *           "name": "brave_summarizer",
 *           "parameters": {
 *             "type": "",
 *             "properties": null,
 *             "required": null
 *           },
 *           "container": {}
 *         },
 *         {
 *           "name": "brave_video_search",
 *           "parameters": {
 *             "type": "",
 *             "properties": null,
 *             "required": null
 *           },
 *           "container": {}
 *         },
 *         {
 *           "name": "brave_web_search",
 *           "parameters": {
 *             "type": "",
 *             "properties": null,
 *             "required": null
 *           },
 *           "container": {}
 *         }
 *       ],
 *       "secrets": [
 *         {
 *           "name": "brave.api_key",
 *           "env": "BRAVE_API_KEY",
 *           "example": "YOUR_API_KEY_HERE"
 *         }
 *       ],
 *       "env": [
 *         {
 *           "name": "BRAVE_MCP_TRANSPORT",
 *           "value": "stdio"
 *         }
 *       ],
 *       "prompts": 0,
 *       "resources": null,
 *       "metadata": {
 *         "pulls": 55668,
 *         "stars": 20,
 *         "githubStars": 311,
 *         "category": "search",
 *         "tags": [
 *           "brave",
 *           "search"
 *         ],
 *         "license": "MIT License",
 *         "owner": "brave"
 *       },
 *       "oauth": {}
 *     }
 *
 *
 * @constructor
 */
const DockerMcpCatalog = () => {
    const { catalog } = useDockerMcpCatalog()
    const [selectedServerKey, setSelectedServerKey] = React.useState<string | null>(null);
    const [selectedServer, setSelectedServer] = React.useState<any | null>(null);
    const [result, setResult] = React.useState<any | null>(null);

    const [searchTerm, setSearchTerm] = React.useState<string>("");
    const [searchFilter, setSearchFilter] = React.useState<any>({"hasTools": false, "hasConfig": false, "hasSecrets": false, "hasOauth": false, "hasNoConfig": false, "hasNoSecrets": false});

    const registry = catalog && catalog?.registry ? catalog.registry : null;

    const itemHasSecrets = (item: any) => {
        return item?.secrets && item?.secrets.length > 0
    }

    const itemHasEnv = (item: any) => {
        return item?.env && item?.env.length > 0
    }

    const itemHasConfig = (item: any) => {
        return item?.config && item?.config.length > 0
    }

    const itemHasOauth = (item: any) => {
        return item?.oauth && item?.oauth.providers && item?.oauth.providers.length > 0
    }

    const toolCount = React.useMemo(() => {
        if (!registry) return 0;
        let count = 0;
        Object.values(registry).forEach((item: any) => {
            if (item.tools && Array.isArray(item.tools)) {
                count += item.tools.length;
            }
        });
        return count;
    }, [registry])

    const filteredRegistry = React.useMemo(() => {
        if (!registry) return {};

        const filtered: { [key: string]: any } = {};

        if (searchTerm.trim() !== "") {
            const lowerSearchTerm = searchTerm.toLowerCase();
            Object.entries(registry).forEach(([key, item]: [string, any]) => {
                if (
                    key.toLowerCase().includes(lowerSearchTerm) ||
                    (item.title && item.title.toLowerCase().includes(lowerSearchTerm)) ||
                    (item.description && item.description.toLowerCase().includes(lowerSearchTerm)) ||
                    (item.tags && item.tags.some((tag: string) => tag.toLowerCase().includes(lowerSearchTerm)))
                ) {
                    filtered[key] = item;
                }
            });
        }

        // apply additional filters
        Object.entries(registry).forEach(([key, item]: [string, any]) => {
            let matches = true;
            if (searchFilter.hasTools && (!item.tools || item.tools.length === 0)) {
                matches = false;
            }
            if (searchFilter.hasConfig && (!itemHasConfig(item) || !itemHasEnv(item))) {
                matches = false;
            }
            if (searchFilter.hasSecrets && !itemHasSecrets(item)) {
                matches = false;
            }
            if (searchFilter.hasOauth && itemHasOauth(item)) {
                matches = false;
            }
            if (searchFilter.hasNoConfig && (itemHasConfig(item) || itemHasEnv(item))) {
                matches = false;
            }
            if (searchFilter.hasNoSecrets && itemHasSecrets(item)) {
                matches = false;
            }
            if (matches) {
                filtered[key] = item;
            }
        });

        return filtered;
    }, [registry, searchTerm, searchFilter]);

    const buildConnectJsonSchemaForServer = (serverDef: any): RJSFSchema => {

        const properties: any = {}

        // env vars
        // const envs = serverDef?.env || []
        // envs.forEach((envVar: any) => {
        //     properties[envVar.name] = {
        //         type: "string",
        //         title: envVar.name,
        //         default: envVar.value || ""
        //     }
        // })
        console.log("serverDev:", serverDef)
        console.log("serverDef config:", serverDef?.config)
        const config = serverDef?.config && Array.isArray(serverDef?.config)
            ? serverDef?.config[0] || {} : {}

        // add secrets
        const secrets = serverDef?.secrets || []
        secrets.forEach((secretVar: any) => {
            properties['secret__' + secretVar.name] = {
                type: "string",
                title: '🔐 Secret: ' + secretVar.name,
                default: "",
                description: `Secret (in env var ${secretVar.env})`
            }
        })

        if (config) {
            config?.properties?.forEach((configVar: any) => {
                const schema = configVar?.Schema || {};
                properties[configVar.Name] = schema
            })
        }

        return {
            type: "object",
            properties: properties,
            required: [],
        }
    }

    const handleSubmit = async ({ formData }: any) => {
        console.log("Connecting to server with data:", formData);

        if (!selectedServer || !selectedServerKey) {
            console.error("No server selected");
            return;
        }

        // create new mcp_server inventory item
        let mcpType;
        let properties: any = {}
        if (selectedServer.type === "server") {
            mcpType = "stdio"
            properties["command"] = "docker"
            properties["args"] = "run --rm -i " + selectedServer.image
        } else if (selectedServer.type === "remote") {
            mcpType = "http"
            properties["url"] = selectedServer.remote.url
        }
        const serverName = selectedServerKey.toUpperCase()
        const item = {
            name: serverName,
            properties: {
                name: serverName,
                type: mcpType,
                ...properties
            }
        }

        console.log("Creating MCP server inventory item:", item);
        //const createdItem = await api.post("/api/inventory/mcp-server", item);
        //console.log(createdItem);
    }

    const typeEmojis: { [key: string]: string } = {
        "server": "🖥️",
        "remote": "☁️",
        "poci": "🧪",
    }

    const getTypeEmoji = (type: string) => {
        return typeEmojis[type] || "❓"
    }

    return (
        <div>
            <div>
                <Input value={searchTerm} placeholder={"Search..."} className={"mb-4"}
                       onChange={(e) => setSearchTerm(e.target.value)} />

                <div className={"flex flex-row mb-4"}>
                    <div className={"mr-4"}>
                        <input type="checkbox" id="hasTools" checked={searchFilter.hasTools}
                               onChange={(e) => setSearchFilter({...searchFilter, hasTools: e.target.checked})} />
                        <label htmlFor="hasTools" className={"ml-1"}>Has Tools</label>
                    </div>
                    <div className={"mr-4"}>
                        <input type="checkbox" id="hasConfig" checked={searchFilter.hasConfig}
                               onChange={(e) => setSearchFilter({...searchFilter, hasConfig: e.target.checked, hasNoConfig: false})} />
                        <label htmlFor="hasConfig" className={"ml-1"}>Requires Config</label>
                    </div>
                    <div className={"mr-4"}>
                        <input type="checkbox" id="hasSecrets" checked={searchFilter.hasSecrets}
                               onChange={(e) => setSearchFilter({...searchFilter, hasSecrets: e.target.checked, hasNoSecrets: false})} />
                        <label htmlFor="hasSecrets" className={"ml-1"}>Requires Secrets</label>
                    </div>
                    <div className={"mr-4"}>
                        <input type="checkbox" id="hasOauth" checked={searchFilter.hasOauth}
                               onChange={(e) => setSearchFilter({...searchFilter, hasOauth: e.target.checked})} />
                        <label htmlFor="hasOauth" className={"ml-1"}>Has Oauth</label>
                    </div>
                    <div className={"mr-4"}>
                        <input type="checkbox" id="hasNoConfig" checked={searchFilter.hasNoConfig}
                               onChange={(e) => setSearchFilter({...searchFilter, hasNoConfig: e.target.checked, hasConfig: false})} />
                        <label htmlFor="hasNoConfig" className={"ml-1"}>No Config Required</label>
                    </div>
                    <div className={"mr-4"}>
                        <input type="checkbox" id="hasNoSecrets" checked={searchFilter.hasNoSecrets}
                               onChange={(e) => setSearchFilter({...searchFilter, hasNoSecrets: e.target.checked, hasSecrets: false})} />
                        <label htmlFor="hasNoSecrets" className={"ml-1"}>No Secrets Required</label>
                    </div>
                </div>
            </div>
            <div className={"flex flex-row mb-2 text-muted-foreground"}>
                {registry && Object.keys(registry).length} servers in registry.{' '}
                {toolCount} tools available.{' '}
                {Object.keys(filteredRegistry).length} servers match filters.
            </div>
            {Object.entries(filteredRegistry).map(([key, item]: any) => {
                return (
                    <div key={key} className={"border px-4 py-2 mb-2 rounded-xl hover:bg-accent"}>
                        <div className={"flex justify-between items-center"}>
                            <div className={"mb-1"}>
                                <h3 className={"font-bold"} title={item?.description} onClick={() => {
                                    setSelectedServerKey(key);
                                    setSelectedServer(item);
                                }}>
                                    {getTypeEmoji(item.type)} {item.title}</h3>
                                <p className={"text-xs text-muted-foreground mb-1 max-h-8 overflow-hidden hover:max-h-16 hover:overflow-y-scroll"}>{item?.description}</p>

                                <div className={"flex flex-row"}>
                                    <div className={"text-xs text-muted-foreground mr-1"}>🛠️ {item?.tools?.length || 0} tools</div>
                                    <div className={"text-xs text-muted-foreground mr-1"}>{(itemHasConfig(item) || itemHasEnv(item)) && ("⚙️ Requires configuration")}</div>
                                    <div className={"text-xs text-muted-foreground mr-1"}>{itemHasSecrets(item) && ("🔑 Requires secrets")}</div>
                                    <div className={"text-xs text-muted-foreground mr-1"}>{itemHasOauth(item) && (`🆔 ${item?.oauth?.providers.length} Oauth provider`)}</div>

                                    <div className={"text-xs text-muted-foreground mr-1"}>
                                        📄 <a rel={"noreferrer noopener"} href={item?.readme} target={"_blank"}>Readme</a>
                                    </div>
                                    <div className={"text-xs text-muted-foreground mr-1"}>
                                        📚 <a rel={"noreferrer noopener"} href={item?.source} target={"_blank"}>Source</a>
                                    </div>
                                </div>
                                {/*<div>
                                    <JsonView src={item} collapsed={true} />
                                </div>*/}
                            </div>
                            <Button variant={"outline"}
                                    size={"sm"}
                                    onClick={() => {
                                        setSelectedServerKey(key);
                                        setSelectedServer(item);
                                    }}>Add Server</Button>
                        </div>
                        {selectedServer?.title === item.title && <div>
                            {item?.tools?.map((tool: any) => (
                                <div key={tool.name}>{tool.name}</div>
                            ))}
                            <Separator className={"my-2"} />
                            <Form schema={buildConnectJsonSchemaForServer(item)}
                                  validator={validator}
                                  onSubmit={handleSubmit}
                            ><Button>Connect</Button></Form>
                            {result && <JsonView src={result} />}
                        </div>}
                    </div>
                )
            })}
        </div>
    );
};

export default DockerMcpCatalog;
