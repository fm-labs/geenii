# Web UI

`geenii-ui/` is the React frontend for the [HTTP server](server.md). The same
code runs in the browser (Vite) and as a desktop app (Tauri 2). A more
detailed component inventory and cleanup list is in
[`geenii-ui/SUMMARY.md`](../../geenii-ui/SUMMARY.md).

**Stack:** React 19, TypeScript, Vite 7, Tailwind 4, shadcn/ui, rjsf
(JSON-Schema forms), lucide icons. There is no router library, no state
library and no tests.

```bash
cd geenii-ui
pnpm dev          # http://localhost:1430 (fixed port, Tauri expects it)
pnpm build        # tsc && vite build -> dist/
pnpm tauri dev    # desktop shell
```

The backend URL comes from `VITE_XAI_API_URL` (default
`http://localhost:33311`). Feature flags are `VITE_FEATURE_*` variables, read
in `src/constants.ts`.

## Boot sequence

```
App.tsx
  ThemeProvider
  └ ServerContextProvider    serverUrl (from VITE_XAI_API_URL)
     └ ApiProvider           api client + fetch helpers bound to serverUrl
        └ AppContextProvider polls GET /api/v1/info; shows "313 – Waiting for geenii" until it answers
           └ AppRouter       hash router (#/path) → page
```

Nothing below `AppContextProvider` renders while the backend is down.

## Calling the backend

Use the `useApi()` hook from `src/context/api-context.tsx`. Do not build URLs
from `XAI_API_URL` yourself.

| Member | Use |
|---|---|
| `fetchJson(path, init?)` | GET/POST that returns parsed JSON; **throws** `ApiError` on non-2xx |
| `fetch(path, init?)` | Plain `fetch` with `path` resolved against the server URL; use it when you need the status or the error body |
| `api` | Typed client (`IAiClient`, `src/api/xai-web.ts`) for `info` and the `/ai/*` endpoints |
| `apiBaseUrl` | The server URL, e.g. for non-fetch consumers |

Relative paths (`/api/v1/tools/`) are resolved against the server URL;
absolute URLs pass through unchanged.

```tsx
const { fetchJson } = useApi()
const [items, setItems] = React.useState<ToolType[]>([])
const [loading, setLoading] = React.useState(true)
const [error, setError] = React.useState<string | null>(null)

const load = React.useCallback(async () => {
  setLoading(true); setError(null)
  try {
    setItems(await fetchJson('/api/v1/tools/'))
  } catch (err) {
    setError(err?.message || 'Unknown error')
  } finally {
    setLoading(false)
  }
}, [fetchJson])

React.useEffect(() => { load() }, [load])
```

Error responses carry a `Problem` body (`{error, status, detail}`, see
[server.md](server.md#errors)). `fetchJson` throws an `ApiError`
(`src/api/api-error.ts`) whose `message` is the Problem `detail`, so
`err.message` is ready to show. It also has `status` and `problem`, and the
axios-style `response.{status,data}`. The xchat backend throws `ChatApiError`,
a subclass.

Put response types next to the feature, e.g. `app/tools/tool-types.ts`.

For the model list use `useModels()` (`src/hooks/use-models.ts`). It loads
`GET /api/v1/ai/models` once per server and shares the result between
components; `modelId(model)` gives the `provider:name` id the completion APIs
expect. Both chat model selectors use it.

## Layout

| Path | Contents |
|---|---|
| `src/app-router.tsx` | Route table; pages read `:params` via `useRoute()` |
| `src/app/<feature>/` | One folder per feature: `*-page.tsx` (wrapped in `MainLayout`, `XchatProvider` for the agent pages, or `ConsoleLayout` for console pages), views, local types |
| `src/components/ui/` | shadcn primitives |
| `src/components/xchat/` | Agent chat component library (see below) |
| `src/components/layout/` | `MainLayout` + `AppSidebar` (main app shell, see below), `ConsoleLayout` + `console-navdata.tsx` (console sidebar), `MainContent`. The old `Layout`/`Headerbar` top nav is no longer used by any page |
| `src/components/tauri/` | Tauri title bar, panel and command helpers |
| `src/context/` | `server-context`, `api-context`, `app-context` |
| `src-tauri/` | Rust shell: plugins, tray, `geenii://` app protocol, sidecar |

## Main layout

`MainLayout` (`components/layout/main-layout.tsx`) wraps every non-console
page in a shadcn `SidebarProvider` (collapsed by default, `--sidebar-width`
350px) with `AppSidebar` and a `SidebarInset` for the page. `AppSidebar` has
two columns:

- an icon rail with the nav items (Start `#/`, Agents `#/agents`, a
  `#/console` link, and placeholder items) and `NavUser` in the footer;
- a wider panel, shown when the sidebar is expanded, with the optional
  `sidebarHeader` slot and the xchat session list
  (`XchatSessionsSidebarGroup`, which needs a surrounding `ChatProvider`).

`XchatProvider` (`app/xchat/xchat-provider.tsx`) is `MainLayout` inside a
`ChatProvider`. It puts a `BackendSwitcher` (echo or any agent from
`GET /agents/`, default `default`) in `sidebarHeader`, so the session list
shows that backend's conversations. `#/agents` and `#/agents/:name` use it;
the agent page adds its own sticky header with a `SidebarTrigger` and
breadcrumb.

Pages render inside `SidebarInset`; `MainContent` no longer offsets for a top
nav.

## Agent launcher (`#/`)

`app/launcher/launcher.view.tsx` is the start page: an app-launcher grid of
agents from `GET /agents/`, sorted by label.

- A search field filters by name, label, description and model; Enter opens
  the first match, Esc clears. While searching, all matches show in one grid.
- Starred agents sit in a dock-style row with larger tiles above the grid
  (and keep a small star badge in the grid). Stars live in `localStorage`
  under `geenii.launcher.starred`; with nothing stored, `default` is starred.
  The backend has no starred flag.
- Each tile is a gradient squircle with the agent's initials; the hue is
  derived from the name, so it is stable. Clicking a tile opens
  `#/agents/<name>`.
- Hovering a tile (about 450 ms) opens a details popover: label, name, scope,
  description, model, tools, skills, MCP servers, working dir, a star toggle,
  **Launch** and a link to `#/console/configure/agents`. The ⓘ button on the
  tile pins the popover open until you click outside.

## Features backed by the current server

| Route | View | Endpoints |
|---|---|---|
| `#/` | `launcher/launcher.view.tsx` — agent launcher (see above) | `GET /agents/` |
| `#/agents` | `agents/agents.view.tsx` — card grid of agents; each card links to the agent page | `GET /agents/` |
| `#/agents/:name` | `agents/agent.view.tsx` + `agent-chat.tsx` — an xchat bound to this agent (no session list, "New chat" starts over), with the agent's short info (model, description, tool/MCP/skill counts) in the chat card header and a Details dialog for parameters, tool and skill descriptions and instructions | `GET /agents/{name}`, `/agents/{name}/commands`, `/tools/`, `/chats/*` |
| `#/console/playground/tools` | `tools/tools.view.tsx` — tools as badges grouped by type; clicking one opens a pane with the parameter table, an rjsf form built from `parameters`, and Execute | `GET /tools/`, `POST /tools/{name}/execute` |
| `#/console/configure/mcp-servers` | `console/components/mcp-servers-settings-view.tsx` — filterable server list; a details card with config (fields or raw JSON), the server's tools, and an rjsf form per tool; an editor to add, edit and delete servers (see [mcp.md](mcp.md#web-ui)) | `GET`/`POST /mcp/servers`, `GET`/`PUT`/`DELETE /mcp/servers/{name}`, `GET /mcp/servers/{name}/config`, `POST /mcp/servers/{name}/tool/call` |
| `#/console/system/info` | `console/components/system-info-view.tsx` — tiles for version and uptime, CPU, memory and disk `/` (with usage bars); cards for directories (copyable), AI providers (configured or not), user, binaries found on `PATH`, environment variables (collapsed; only the allow-listed, redacted ones unless `DEV_MODE=1`) and the raw JSON (collapsed) | `GET /info` |
| `#/console/playground/xchat` | `xchat/xchat-demo-page-1.tsx` | `/chats/*`, `/agents/{name}/commands` |
| `#/console/playground/completions`, `#/chat`, `#/completions`, `#/audio` | completion chat and quick generators (completion pages use `ConsoleLayout`) | `/ai/*` |

### Console

`#/console` is the admin area; its sidebar comes from
`src/components/layout/console-navdata.tsx`.

| Route | Page | Sections |
|---|---|---|
| `#/console/playground/{completions,tools,xchat}` | completion chat, tools view, xchat demo | — |
| `#/console/configure/:section` | `console/configure-page.tsx` (formerly `managed-page.tsx`, `#/console/managed/…`) | `agents`, `skills`, `mcp-servers` (installed servers), `models`; `tools` is in the nav but not rendered yet |
| `#/console/catalog/:section` | `catalog/catalog-page.tsx` | `mcp` (Docker MCP Catalog, `DockerMcpCatalogView`), `models` |
| `#/console/system/:section` | `console/system-page.tsx` | `info`, `stats` (usage stats), `settings` |

Environments, Memory Stores, Vaults and Plugins entries are commented out in
the nav.

### Docker MCP Catalog

`DockerMcpCatalogView` (`catalog/docker-mcp-catalog-view.tsx`) and
`catalog/docker-mcp-catalog-page.tsx` both render `DockerMcpCatalogOci` inside
`DockerMcpCatalogProvider` (`src/app/catalog/components/`). The provider loads the OCI-format catalog
from `public/assets/docker-mcp-catalog-oci.json` (`{ref, source, title,
digest, servers[]}`, each server record holding its definition under
`snapshot.server`) and looks servers up by name with `getServerDef()`.
`DockerMcpCatalogConfigBuilder` shows the `mcpServers` entry to add to
`mcp.json`; nothing is installed through the server yet.

The components for the previous catalog format
(`docker-mcp-catalog-v3.json`) are kept with a `V3` suffix
(`DockerMcpCatalogV3`, `DockerMcpCatalogV3Provider`,
`DockerMcpCatalogV3ConfigBuilder`) and are deprecated.

Other pages (`#/mcp`, `#/flows`, parts of `#/settings`, apps) call endpoints the server does not have yet; see
`geenii-ui/SUMMARY.md`.

### xchat

`components/xchat/` is a self-contained chat UI: `Chat`, `ChatProvider` and
`useChat(selector)`, message and content-part renderers (`parts/`), a slash
command menu and voice input. It talks to a pluggable `ChatBackend`:

- `createAgentBackend({ baseUrl, … })` uses the `/chats` API: it creates
  sessions, reads the NDJSON turn stream, answers approval requests and
  cancels turns. Slash commands come from `/agents/{name}/commands`.
- `createEchoBackend()` is an offline backend for UI work.

`widget` content parts are drawn by the widgets in `parts/widgets/`; see
[Widgets](widgets.md).

Assistant messages that carry `usage` (see
[messages.md](messages.md#modelmessage-geeniidatamodelspy)) show the call's
total tokens in the message header, with input, cache, output and time in a
tooltip (`chat-message-usage.tsx`).
