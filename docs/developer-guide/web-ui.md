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
| `src/app/<feature>/` | One folder per feature: `*-page.tsx` (wrapped in `Layout`), views, local types |
| `src/components/ui/` | shadcn primitives |
| `src/components/xchat/` | Agent chat component library (see below) |
| `src/components/layout/` | `Layout` (top nav, flag-driven), `MainContent` |
| `src/components/tauri/` | Tauri title bar, panel and command helpers |
| `src/context/` | `server-context`, `api-context`, `app-context` |
| `src-tauri/` | Rust shell: plugins, tray, `geenii://` app protocol, sidecar |

## Features backed by the current server

| Route | View | Endpoints |
|---|---|---|
| `#/` (dashboard), `#/agents` | `agents/agents.view.tsx` — card grid of agents; each card links to the agent page | `GET /agents/` |
| `#/agents/:name` | `agents/agent.view.tsx` + `agent-chat.tsx` — an xchat bound to this agent (no session list, "New chat" starts over), with the agent's short info (model, description, tool/MCP/skill counts) in the chat card header and a Details dialog for parameters, tool and skill descriptions and instructions | `GET /agents/{name}`, `/agents/{name}/commands`, `/tools/`, `/chats/*` |
| `#/` (dashboard), `#/tools`, settings | `tools/tools.view.tsx` — tools as badges grouped by type; clicking one opens a pane with the parameter table, an rjsf form built from `parameters`, and Execute | `GET /tools/`, `POST /tools/{name}/execute` |
| `#/xchat` | `xchat/xchat-demo-page-1.tsx` | `/chats/*`, `/agents/{name}/commands` |
| `#/chat`, `#/completions`, `#/audio` | completion chat and quick generators | `/ai/*` |

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
