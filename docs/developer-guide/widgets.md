# Widgets

A **widget** is a content part that asks the chat UI to render something richer
than text: a table, a chart, a progress bar, a button. The message only names
the widget and carries its data; the UI decides how to draw it. A UI that does
not know the widget shows a fallback text instead, so a widget message is
always readable.

Widgets are usually sent in system messages (status, results, notifications),
but any message may contain them; nothing checks the role.

## The content part

`WidgetContent` in `src/geenii/chat_models.py`, mirrored by `WidgetContent` in
`geenii-ui/src/components/xchat/chat.types.ts`:

| Field     | Type             | Meaning |
|-----------|------------------|---------|
| `type`    | `"widget"`       | Discriminator |
| `name`    | str              | Widget name in dot-notation, e.g. `geenii.table`. `geenii.*` is reserved for the built-ins; use your own prefix (`acme.weather`) for custom widgets |
| `data`    | any JSON, optional | Passed to the widget as-is. Its shape is defined by each widget (see [Built-in widgets](#built-in-widgets)) |
| `heading` | str, optional    | Small header the UI renders above the widget (and above the fallback) |
| `text`    | str, optional    | Fallback, rendered as markdown when the UI does not know the widget |

`to_text()` returns `heading` and `text` on separate lines, or
`[widget: <name>]` if there is no text. That is what providers see when a
widget ends up in a model's context, so write `text` as a useful plain summary
of the data, not as "see the widget".

`heading` is a different thing from the `title` that several widgets accept
inside `data`: the heading is drawn by the chat around any widget, a data
title is drawn by the widget itself, inside its frame.

## Sending a widget

From Python, for example from an agent task:

```python
from geenii.chat_models import TextContent, WidgetContent
from geenii.datamodels import SystemMessage

yield SystemMessage(level="info", content=[
    TextContent(text="Connected MCP servers:"),
    WidgetContent(
        name="geenii.table",
        heading="MCP servers",
        data={"columns": ["server", "tools"], "rows": [["filesystem", 7], ["weather", 2]]},
        text="MCP servers: filesystem (7 tools), weather (2 tools)",
    ),
])
```

On the wire (the chat NDJSON stream and the history) the part is plain JSON:

```json
{"type": "widget", "name": "geenii.table", "heading": "MCP servers",
 "data": {"columns": ["server", "tools"], "rows": [["filesystem", 7], ["weather", 2]]},
 "text": "MCP servers: filesystem (7 tools), weather (2 tools)"}
```

No server code sends widgets yet; the echo backend's demos are the only
senders (see [Trying them out](#trying-them-out)).

## How the UI renders a widget

`WidgetPart` (`parts/widget-parts.tsx`) is the renderer for the `widget`
content type:

1. It looks `name` up in the widgets passed to `<ChatProvider widgets={…}>`,
   then in the built-in `defaultWidgets` (`parts/widgets/index.ts`). So an app
   can add widgets and override built-ins.
2. A known widget is rendered with `{ data, part, message }`
   (`WidgetRendererProps`); `data` is `null` when the part has none.
3. An unknown widget renders `text` as markdown; without `text` it shows
   `[widget: <name>]` and the data as JSON.
4. If `heading` is set, it is shown as a small muted header above 2 or 3.

Each widget is wrapped in an error boundary (`WidgetErrorBoundary`). If it
throws while rendering, for example on malformed data, the message shows the
fallback from step 3 with a note "Widget <name> could not be displayed", and
the error is logged with `console.warn`. The rest of the chat is not affected.
The boundary resets when the part changes, so a later update with valid data
renders normally. Errors in event handlers, timers or async code (say, a click
handler) are not caught by the boundary; widgets handle those themselves.

**System messages with a widget** are rendered as full-width cards instead of
the small centered notices used for plain text system messages
(`chat-message.tsx`). The card is tinted by `level`; `warning` and `error`
cards show the level icon, `info` cards show none.

## Built-in widgets

All built-ins live in `geenii-ui/src/components/xchat/parts/widgets/` (paths
below are relative to `geenii-ui/src/components/xchat/`), one file
per widget, and need no extra dependencies. Every field of `data` is
optional unless noted; `x = v` means the default is `v`. Missing data, or a
field of the wrong type (say, `rows` that is not an array), renders an empty or
"invalid" state. Malformed entries inside a list, such as a `null` row or step,
are not checked; if they make the widget throw, the error boundary shows the
fallback instead (see [How the UI renders a widget](#how-the-ui-renders-a-widget)).

### Data

| Name | `data` | Notes |
|---|---|---|
| `geenii.table` | `{ columns?, rows }` | `rows` (required) are arrays or objects. Without `columns`, the keys of object rows become the columns. Scrolls above 384 px |
| `geenii.list` | `{ items, ordered? = false }` | Items are strings or `{ text, description? }` |
| `geenii.keyvalue` | `{ title?, items: [{ key, value }] }` or a plain object | Two-column grid; object values are shown as JSON |
| `geenii.json` | `{ value, title?, expand? = 2 }` | Collapsible tree, colored by type; `expand` = levels open at first |
| `geenii.csv` | `{ csv, delimiter?, header? = true, title? }` | Parsed (RFC 4180 quoting, CRLF) and shown as a table. Without `delimiter`, the most frequent of `,` `;` tab `\|` in the first line is used |

### Charts and numbers

| Name | `data` | Notes |
|---|---|---|
| `geenii.barchart` | `{ title?, unit?, max?, items: [{ label, value }] }` | Horizontal CSS bars; `max` defaults to the largest value |
| `geenii.linechart` | `{ title?, unit?, series: [{ name, points: [{ x, y }] }] }` | SVG; `x` is a number or an ISO date. Min/max labels, a tooltip per point, a legend for several series. Colors are the theme's `--chart-1`…`--chart-5` |
| `geenii.donut` | `{ title?, unit?, items: [{ label, value, color? }], hole? = true }` | Donut chart (`hole: false`: pie) with the total in the middle and a legend with values and percentages. Items with a value ≤ 0 are left out. Colors: `--chart-1`…`--chart-5`, repeating, unless `color` is set |
| `geenii.gauge` | `{ value, min? = 0, max? = 100, label?, unit?, thresholds?: { warning?, error? } }` | Half-circle meter. Turns amber from `thresholds.warning` and red from `thresholds.error` (both in the same units as `value`) |
| `geenii.heatmap` | `{ title?, unit?, weeks?, days: [{ date, value }] }` | GitHub-style activity grid: a column per week (Monday on top), ending with the latest date, month names on top, a tooltip per day. `date` is `YYYY-MM-DD` (invalid dates are skipped, values on the same day are added up). `weeks` defaults to the span of the data, at most 53. Four color steps relative to the highest value |
| `geenii.stat` | `{ items: [{ label, value, unit?, delta? }] }` | Big-number tiles; `delta` is a percentage, shown as green ▲ or red ▼ |

### Status and time

| Name | `data` | Notes |
|---|---|---|
| `geenii.progress` | `{ label?, value?, max? = 100, status? = running }` | `status`: `running`, `done` (green), `error` (red, "failed"). Without `value` the bar pulses (indeterminate) |
| `geenii.steps` | `{ title?, steps: [{ text, status? = pending, detail? }] }` | A plan with a status icon per step: `pending`, `running`, `done`, `failed`, `skipped` |
| `geenii.timeline` | `{ title?, items: [{ time, title, description?, level? = info }] }` | `time` is an ISO datetime; the dot color follows `level` (`info`, `warning`, `error`) |
| `geenii.weather` | `{ location?, unit? = C, wind_unit? = km/h, current?: { temp, condition?, icon?, feels_like?, humidity?, wind? }, forecast?: [{ day, condition?, icon?, high?, low?, precip? }] }` | Current conditions and a forecast row. The emoji is derived from `condition` ("Light rain" → 🌧️) unless `icon` is given; `day` is a label or an ISO date (shown as weekday); `precip` in % |
| `geenii.clock` | `{ timezone?, label? }` | Live clock; `timezone` is an IANA name such as `Europe/Vienna` |
| `geenii.countdown` | `{ until, label? }` | `until` is an ISO datetime; shows the time left, then "Done" |

### Code and files

| Name | `data` | Notes |
|---|---|---|
| `geenii.code` | `{ code, language?, filename? }` | Copy button; no syntax highlighting |
| `geenii.diff` | `{ diff, filename? }` | `diff` is unified diff text computed by the sender; colors added/removed lines, counts them, copy button |
| `geenii.filetree` | `{ root?, entries: [{ path, size?, type? }], expand? = 2 }` | Builds a tree from `/`-separated paths; folders first. An entry is a folder if `type` is `dir` or the path ends with `/` |

### Embedded content and actions

| Name | `data` | Notes |
|---|---|---|
| `geenii.links` | `{ items: [{ title?, url, snippet?, source? }], limit? = 5 }` | Search or web results: source or host, linked title, two-line snippet. Shows `limit` items with a "Show all" toggle. Only `http(s)` urls become links |
| `geenii.html` | `{ html, height? = 240, title? }` | `html` is shown in a sandboxed iframe (`srcDoc`); scripts run, but in an opaque origin without access to the app |
| `geenii.iframe` | `{ url, scripts? = false, trusted? = false, height? = 320, title? }` | Embeds a page. Loads only after a click unless `trusted`; scripts only with `scripts`. "Open" opens the url in a new window |
| `geenii.postbutton` | `{ url, payload?, label? = Send, expect? = 200, confirm?, repeat? = false, headers? }` | On click, POSTs `payload` as JSON. Success only on status `expect`. `confirm` asks a question first; after a success the button stays done unless `repeat` |

### Layout

| Name | `data` | Notes |
|---|---|---|
| `geenii.tabs` | `{ tabs: [{ label, widget?: { name, data?, heading?, text? }, text? }], active? = 0 }` | Tabs, each holding a nested widget or markdown `text`. Nested widgets go through the same rendering as top-level ones (lookup, heading, fallback, their own error boundary), so tabs can hold any widget, including custom ones and other tabs. Only the active tab is mounted: switching tabs resets the state of the widget left (a running game, a typed form). Arrow keys, Home and End move between tabs |

### Replies

These widgets answer in the chat: they send a **plain user message**, exactly
as if the user had typed it, so they work with every backend and the agent
reads the answer as normal input. They are disabled while a turn is running
(the session handles one turn at a time).

With `once` (the default), a widget locks as soon as the conversation has moved
on: when any user message follows the widget's message, including one the user
typed instead. This is derived from the history, so it also holds after
reloading a conversation.

| Name | `data` | Notes |
|---|---|---|
| `geenii.choices` | `{ options: (string \| { label, message? })[], once? = true }` | Suggested replies as buttons. A click sends the option's `message`, or its label. The option matching the answer is highlighted |
| `geenii.rating` | `{ type? = stars, max? = 5, comment? = false, once? = true }` | `type`: `stars` (`max` 3–10) or `thumbs`. Without `comment` a click sends right away; with it, the click selects and "Send" sends the rating with an optional comment. Message: `Rating: ★★★★☆ (4/5)` or `Rating: 👍 helpful`, then `Comment: …` |
| `geenii.form` | `{ fields: [{ name, label?, type? = text, required?, options?, default?, placeholder? }], submit? = Send, format? = text, once? = true }` | Types: `text`, `textarea`, `number`, `select` (with `options`), `checkbox`, `date`, `email`, `url`. Uses browser validation (`required`, number, email…). Sends one message: `Label: value` lines with empty fields left out (`format: text`), or a JSON code block with every field (`format: json`) |

### Easter eggs

| Name | `data` | Notes |
|---|---|---|
| `geenii.matrix` | `{ text?, height? = 160, seconds? }` | Digital rain on a canvas; `text` fades in after 2 s; stops after `seconds` (default: never) |
| `geenii.terminal` | `{ lines?, prompt? = C:\>, speed? = 30 }` | Green-screen terminal that types `lines` (default: a boot sequence), `speed` ms per character |
| `geenii.snake` | `{ size? = 16, speed? = 120 }` | Playable Snake: click it, then arrows/WASD; space starts, pauses and restarts. Pauses when it loses focus |
| `geenii.fortune` | `{ fortune?, width? = 40 }` | cowsay bubble; a random built-in fortune if none is given |
| `geenii.dice` | `{ count? = 1, values? }` | Up to 10 dice; `values` are pre-rolled results (1–6). "Roll" rolls again in the browser |

Animated widgets (matrix, terminal, dice) show their end state when the user
has asked the OS for reduced motion.

### Development aids

| Name | `data` | Notes |
|---|---|---|
| `geenii.dev.errorboundarytest` | `{ message? = Widget crashed on purpose, delay? = 0 }` | Throws while rendering, to see the [error boundary](#how-the-ui-renders-a-widget) at work: the message shows the fallback `text` and a note. With `delay` (ms) it first renders a countdown and crashes on a later re-render |

## Security

Widget data comes from the server, and through it from agents and tools, so
treat it as untrusted:

- **Text is never HTML.** All widgets render data as text through React. The
  fallback `text` is markdown, rendered without raw HTML.
- **`geenii.html`** runs in `sandbox="allow-scripts"` without
  `allow-same-origin`: scripts run in an opaque origin and cannot reach the
  app's DOM, cookies or storage.
- **`geenii.iframe`** only accepts `http(s)` urls (no `javascript:`, `data:` or
  `file:`), sends no referrer, and loads untrusted pages only after a click.
  Without `scripts` the frame is fully sandboxed. With `scripts`, a page from
  another origin keeps its own origin; a page from the app's own origin does
  not, because scripts plus same-origin could lift the sandbox.
- **`geenii.choices` and `geenii.form`** only send on a click, and what they
  send is a visible user message in the chat, never a hidden request.
- **`geenii.links`** only links `http(s)` urls, opened in a new window without
  access back to the app (`noopener noreferrer`).
- **`geenii.postbutton`** only acts on a click, shows the target
  (`POST host/path`) under the button, sends no cookies
  (`credentials: 'omit'`) and times out after 15 s. Use `confirm` for anything
  with side effects.
- **Desktop app (Tauri):** the CSP in `geenii-ui/src-tauri/tauri.conf.json`
  limits what widgets can reach. `frame-src` only allows the app and the
  geenii server, so `geenii.iframe` cannot show external pages there (its
  "Open" button still works). `connect-src` allows `https:` and the geenii
  server, so `geenii.postbutton` cannot post to other plain `http:` hosts.

## Adding a widget

### In an app (custom widgets)

Pass a map of name → component to the provider. The map is added to the
built-ins and wins over them:

```tsx
import { ChatProvider, WidgetRendererProps } from '@/components/xchat'

type WeatherData = { city: string; temp: number }

const WeatherWidget = ({ data }: WidgetRendererProps<WeatherData | null>) => (
  <div className={'rounded-md border px-3 py-2'}>
    {data?.city ?? '?'}: {data?.temp ?? '–'} °C
  </div>
)

// defined once, outside the component: a new object on every render re-renders all messages
const widgets = { 'acme.weather': WeatherWidget }

<ChatProvider backend={backend} widgets={widgets}>…</ChatProvider>
```

A widget gets `data` (typed by you, but not validated: it is whatever the
server sent, or `null`), the whole `part` (`name`, `heading`, `text`) and the
`message` it belongs to. `useChatWidgets()` returns the provider's map.

### As a built-in

1. Add `parts/widgets/<name>.tsx` exporting `<Name>Widget`. Start the file
   with a doc comment naming the widget and its `data` shape, like the others.
2. Register it in `parts/widgets/index.ts`: import, export, and an entry in
   `defaultWidgets` (`'geenii.<name>': <Name>Widget`).
3. Add a sample to `sampleWidgetMessages()` in
   `components/xchat/backends/echo-examples.ts`, so `/widgets` shows it.
4. Add it to the reference above.

Conventions the built-ins follow:

- **Be defensive about `data`.** Check arrays with `Array.isArray`, give every
  field a default, and render an empty or "invalid" state instead of throwing.
  The error boundary is a safety net, not the plan: it replaces the whole
  widget with its fallback.
- **No new dependencies.** Plain React, Tailwind, SVG/canvas, lucide icons and
  the shadcn components in `components/ui/`.
- **Use theme tokens** (`text-muted-foreground`, `bg-muted`, `border`,
  `text-destructive`, `--chart-*`) so the widget works in light and dark mode.
  The easter eggs' fixed retro colors are the exception.
- **Keep it bounded.** Long content scrolls inside the widget (`max-h-96
  overflow-auto`) rather than growing the chat.
- **Clean up.** Clear timers and cancel animation frames and requests on
  unmount. Shared helpers: `useNow` (1 s clock), `useReducedMotion`,
  `CopyButton`, `safeUrl` (http(s)-only url check), `useChatReply` (send a
  reply, busy and answered state).
- **Nothing happens without a click.** Widgets that load remote content or
  send requests wait for the user unless the sender opts in (`trusted`).

## Trying them out

The offline echo backend (`backends/echo-backend.ts`) sends widgets as system
messages:

- `/widgets` streams one sample per built-in widget, plus an unknown widget
  that shows its fallback text, grouped like the reference above. Each group
  starts with a small system text message naming the group and its widgets.
  `/example` includes them too.
- Hidden commands, not listed in the command menu: `/matrix`, `/boot`
  (terminal), `/snake`, `/fortune`, `/dice`, and `/crash` (an
  error-boundary test widget that crashes after 3 s).

The samples are in `sampleWidgetMessages()` (built with a `group(title, …)`
helper that adds the separator) and `sampleEasterEggs()` in
`backends/echo-examples.ts`. The `geenii.iframe` and `geenii.postbutton`
samples need network access (wikipedia.org, example.com, httpbin.org).
