// Offline sample data for the echo backend's "example" turn (data URLs, so nothing is fetched).

import type { ContentPart, SystemMessageLevel } from '../chat.types.ts'

const toBase64 = (bytes: Uint8Array): string => {
  let binary = ''
  for (let i = 0; i < bytes.length; i += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000))
  }
  return btoa(binary)
}

const textBytes = (text: string) => new TextEncoder().encode(text)

/** A simple labeled SVG picture as raw base64 (no data: prefix). */
export const sampleSvgBase64 = (label: string, color: string, width = 320, height = 180): string =>
  toBase64(textBytes(
    `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">` +
    `<rect width="100%" height="100%" rx="16" fill="${color}"/>` +
    `<circle cx="${width * 0.2}" cy="${height * 0.5}" r="${height * 0.22}" fill="white" fill-opacity="0.35"/>` +
    `<text x="50%" y="54%" text-anchor="middle" font-family="sans-serif" font-size="${height * 0.14}" fill="white">${label}</text>` +
    `</svg>`,
  ))

export const sampleSvgDataUrl = (label: string, color: string, width?: number, height?: number): string =>
  `data:image/svg+xml;base64,${sampleSvgBase64(label, color, width, height)}`

/** A short sine beep as a 16-bit mono WAV data URL. */
export const sampleBeepDataUrl = (seconds = 0.6, frequency = 660, sampleRate = 8000): string => {
  const samples = Math.floor(seconds * sampleRate)
  const buffer = new ArrayBuffer(44 + samples * 2)
  const view = new DataView(buffer)
  const ascii = (offset: number, s: string) => [...s].forEach((c, i) => view.setUint8(offset + i, c.charCodeAt(0)))

  ascii(0, 'RIFF')
  view.setUint32(4, 36 + samples * 2, true)
  ascii(8, 'WAVE')
  ascii(12, 'fmt ')
  view.setUint32(16, 16, true)          // fmt chunk size
  view.setUint16(20, 1, true)           // PCM
  view.setUint16(22, 1, true)           // mono
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * 2, true)
  view.setUint16(32, 2, true)           // block align
  view.setUint16(34, 16, true)          // bits per sample
  ascii(36, 'data')
  view.setUint32(40, samples * 2, true)
  for (let i = 0; i < samples; i++) {
    const fade = Math.min(1, i / 200, (samples - i) / 200)
    view.setInt16(44 + i * 2, Math.sin((2 * Math.PI * frequency * i) / sampleRate) * 0x3000 * fade, true)
  }
  return `data:audio/wav;base64,${toBase64(new Uint8Array(buffer))}`
}

export const SAMPLE_FILE_TEXT = 'Hello from the echo backend!\nThis file is generated in the browser.\n'

export const sampleTextFile = () => {
  const bytes = textBytes(SAMPLE_FILE_TEXT)
  return { url: `data:text/plain;base64,${toBase64(bytes)}`, size: bytes.length }
}

/** One system message per level, as the agent sends them (e.g. a skill that could not be found). */
export const SAMPLE_SYSTEM_MESSAGES: { level: SystemMessageLevel, text: string }[] = [
  { level: 'info', text: "Skill 'summarize' could not be found." },
  { level: 'warning', text: 'Maximum number of tasks almost reached: 18 of 20.' },
  { level: 'error', text: 'An error occurred while processing the task: connection refused.' },
]

/** Easter-egg widget messages, keyed by the (hidden) echo command that sends them */
export const sampleEasterEggs = (): Record<string, { level: SystemMessageLevel, content: ContentPart[] }> => ({
  matrix: {
    level: 'info',
    content: [{
      type: 'widget',
      name: 'geenii.matrix',
      data: { text: 'Wake up, Neo…', seconds: 15 },
      text: '`Wake up, Neo…`',
    }],
  },
  boot: {
    level: 'info',
    content: [{
      type: 'widget',
      name: 'geenii.terminal',
      data: {},
      text: '```\nGEENII BIOS v0.3.4\nMemory test: 640K OK\nREADY.\n```',
    }],
  },
  snake: {
    level: 'info',
    content: [{
      type: 'widget',
      name: 'geenii.snake',
      title: 'Snake',
      data: { size: 16, speed: 120 },
      text: '🐍 You found the snake. Try a client that supports widgets.',
    }],
  },
  fortune: {
    level: 'info',
    content: [{
      type: 'widget',
      name: 'geenii.fortune',
      title: 'Fortune cookie',
      data: {},
      text: '🥠 It works on my machine.',
    }],
  },
  dice: {
    level: 'info',
    content: [{
      type: 'widget',
      name: 'geenii.dice',
      title: 'Dice',
      data: { count: 2 },
      text: '🎲 You rolled the dice.',
    }],
  },
})

const SAMPLE_CODE ='def hello(name: str) -> str:\n    return f"Hello, {name}!"\n'

const SAMPLE_DIFF = `--- a/src/geenii/config.py
+++ b/src/geenii/config.py
@@ -12,6 +12,8 @@ def load_config(path: str) -> dict:
     with open(path) as f:
-        return json.load(f)
+        data = json.load(f)
+    validate_config(data)
+    return {**DEFAULTS, **data}


 def save_config(path: str, data: dict) -> None:
`

const hoursAgo = (hours: number) => new Date(Date.now() - hours * 3_600_000).toISOString()

/** ISO dates of the last `days` days, oldest first */
const daysAgo = (days: number) => Array.from({ length: days }, (_, i) => hoursAgo((days - 1 - i) * 24))

/**
 * System messages with one example per built-in widget (plus an unknown one, which shows its text),
 * as the server would send them. Built per call, since some data is relative to the current time.
 */
export const sampleWidgetMessages = (): { level: SystemMessageLevel, content: ContentPart[] }[] => [
  {
    level: 'info',
    content: [
      { type: 'text', text: 'Scheduled task **daily-report** runs at 18:00 UTC. Current time:' },
      { type: 'widget', name: 'geenii.clock', data: { timezone: 'UTC', label: 'UTC' }, text: 'Current time: see your clock (UTC).' },
    ],
  },
  {
    level: 'info',
    content: [
      { type: 'text', text: 'Connected MCP servers:' },
      {
        type: 'widget',
        name: 'geenii.table',
        data: {
          columns: ['server', 'tools', 'status'],
          rows: [['filesystem', 7, 'ok'], ['weather', 2, 'ok'], ['whisper', 2, 'starting']],
        },
        text: 'MCP servers: filesystem (7 tools, ok), weather (2 tools, ok), whisper (2 tools, starting)',
      },
    ],
  },
  {
    level: 'info',
    content: [
      { type: 'text', text: 'Skills loaded for this conversation:' },
      {
        type: 'widget',
        name: 'geenii.list',
        data: {
          items: [
            { text: 'summarize', description: 'Summarize long texts and documents' },
            { text: 'translate', description: 'Translate between languages' },
            'weather',
          ],
        },
        text: '- summarize\n- translate\n- weather',
      },
    ],
  },
  {
    level: 'info',
    content: [
      { type: 'text', text: 'Token usage of this conversation by model:' },
      {
        type: 'widget',
        name: 'geenii.barchart',
        data: {
          unit: 'k',
          items: [{ label: 'claude-sonnet-5-5', value: 48.2 }, { label: 'llama3.2', value: 12.7 }, { label: 'whisper', value: 3.1 }],
        },
        text: 'Token usage: claude-sonnet-5-5 48.2k, llama3.2 12.7k, whisper 3.1k',
      },
    ],
  },
  {
    level: 'info',
    content: [
      { type: 'text', text: 'The agent rendered a preview:' },
      {
        type: 'widget',
        name: 'geenii.html',
        data: {
          height: 120,
          title: 'Preview',
          html: '<body style="font-family:sans-serif;margin:12px"><h3 style="margin:0 0 8px">Sandboxed HTML</h3>'
            + '<button onclick="this.textContent=\'Clicked!\'">Click me</button></body>',
        },
        text: 'An HTML preview (not shown).',
      },
    ],
  },
  {
    level: 'info',
    content: [
      { type: 'text', text: 'The agent found a page (untrusted, loads on click):' },
      {
        type: 'widget',
        name: 'geenii.iframe',
        data: { url: 'https://en.wikipedia.org/wiki/Special:Random', scripts: true, height: 360 },
        text: 'A random Wikipedia page: https://en.wikipedia.org/wiki/Special:Random',
      },
    ],
  },
  {
    level: 'info',
    content: [
      { type: 'text', text: 'A trusted page, loaded right away without scripts:' },
      {
        type: 'widget',
        name: 'geenii.iframe',
        data: { url: 'https://example.com', trusted: true, height: 200, title: 'example.com' },
        text: 'https://example.com',
      },
    ],
  },
  {
    level: 'info',
    content: [
      { type: 'text', text: 'Indexing the workspace…' },
      { type: 'widget', name: 'geenii.progress', data: { label: 'Indexing files', value: 42, max: 120 }, text: 'Indexing files: 42/120' },
    ],
  },
  {
    level: 'info',
    content: [
      { type: 'widget', name: 'geenii.progress', title: 'Model download', data: { label: 'Downloading model llama3.2' }, text: 'Downloading model llama3.2…' },
    ],
  },
  {
    level: 'error',
    content: [
      { type: 'text', text: 'Pulling the model failed.' },
      { type: 'widget', name: 'geenii.progress', data: { label: 'Pulling mistral', value: 63, status: 'error' }, text: 'Pulling mistral failed at 63%.' },
    ],
  },
  {
    level: 'info',
    content: [
      {
        type: 'widget',
        name: 'geenii.keyvalue',
        data: {
          title: 'Session',
          items: [
            { key: 'Agent', value: 'echo' },
            { key: 'Model', value: 'claude-sonnet-5-5' },
            { key: 'Context', value: 'a1b2c3d4' },
            { key: 'Tools', value: { allowed: ['filesystem', 'weather'], approval: 'ask' } },
          ],
        },
        text: 'Session: agent echo, model claude-sonnet-5-5',
      },
    ],
  },
  {
    level: 'warning',
    content: [
      { type: 'text', text: 'This conversation is getting long; consider starting a new one.' },
      {
        type: 'widget',
        name: 'geenii.stat',
        data: {
          items: [
            { label: 'Context used', value: 182, unit: 'k tokens', delta: 24 },
            { label: 'Avg. latency', value: 840, unit: 'ms', delta: -12 },
          ],
        },
        text: 'Context used: 182k tokens (+24%), avg. latency 840 ms (-12%)',
      },
    ],
  },
  {
    level: 'error',
    content: [
      { type: 'text', text: 'The hook script failed with exit code 1:' },
      {
        type: 'widget',
        name: 'geenii.code',
        data: { filename: 'hooks/hello.py', language: 'python', code: SAMPLE_CODE },
        text: '```python\n' + SAMPLE_CODE + '```',
      },
    ],
  },
  {
    level: 'warning',
    content: [
      { type: 'text', text: 'Rate limit reached. The next request is possible in:' },
      {
        type: 'widget',
        name: 'geenii.countdown',
        data: { until: new Date(Date.now() + 90_000).toISOString(), label: 'Rate limit reset' },
        text: 'Rate limit resets in 90 seconds.',
      },
    ],
  },
  {
    level: 'info',
    content: [
      { type: 'text', text: 'Configuration reloaded:' },
      {
        type: 'widget',
        name: 'geenii.json',
        data: {
          title: 'geenii.json',
          expand: 1,
          value: {
            agent: { name: 'echo', model: 'claude-sonnet-5-5', temperature: 0.7 },
            mcp_servers: ['filesystem', 'weather', 'whisper'],
            tools: { approval: 'ask', timeout: 30, debug: false, proxy: null },
          },
        },
        text: 'Configuration reloaded.',
      },
    ],
  },
  {
    level: 'info',
    content: [
      { type: 'text', text: 'Exported the task history:' },
      {
        type: 'widget',
        name: 'geenii.csv',
        data: {
          title: 'tasks.csv',
          csv: 'task;status;duration\ndaily-report;done;12.4 s\n"index; workspace";running;\n"say ""hi""";failed;0.3 s\n',
        },
        text: 'Task history exported (3 tasks).',
      },
    ],
  },
  {
    level: 'info',
    content: [
      { type: 'text', text: 'Working on the task **refactor the config loader**:' },
      {
        type: 'widget',
        name: 'geenii.steps',
        data: {
          title: 'Plan',
          steps: [
            { text: 'Read the current config loader', status: 'done' },
            { text: 'Write tests for the existing behavior', status: 'done', detail: '12 tests, all passing' },
            { text: 'Split loading and validation', status: 'running' },
            { text: 'Migrate the YAML loader', status: 'failed', detail: 'yaml module not installed' },
            { text: 'Update the docs', status: 'skipped' },
            { text: 'Run the full test suite' },
          ],
        },
        text: 'Plan: 2 of 6 steps done, 1 running, 1 failed.',
      },
    ],
  },
  {
    level: 'warning',
    content: [
      { type: 'text', text: 'The agent wants to change a file. Review the changes:' },
      {
        type: 'widget',
        name: 'geenii.diff',
        data: { filename: 'src/geenii/config.py', diff: SAMPLE_DIFF },
        text: 'Proposed change to src/geenii/config.py:\n```diff\n' + SAMPLE_DIFF + '```',
      },
    ],
  },
  {
    level: 'info',
    content: [
      { type: 'text', text: 'Token usage over the last 7 days:' },
      {
        type: 'widget',
        name: 'geenii.linechart',
        data: {
          unit: 'k',
          series: [
            { name: 'input', points: daysAgo(7).map((x, i) => ({ x, y: [42, 38, 55, 61, 47, 72, 66][i] })) },
            { name: 'output', points: daysAgo(7).map((x, i) => ({ x, y: [12, 9, 18, 21, 14, 25, 19][i] })) },
          ],
        },
        text: 'Token usage last 7 days: input 381k, output 118k.',
      },
    ],
  },
  {
    level: 'info',
    content: [
      { type: 'text', text: 'Recent runs of the scheduled task **daily-report**:' },
      {
        type: 'widget',
        name: 'geenii.timeline',
        data: {
          items: [
            { time: hoursAgo(50), title: 'Run completed', description: 'Report sent to 3 recipients.' },
            { time: hoursAgo(26), title: 'Run completed with warnings', description: '1 data source was unavailable.', level: 'warning' },
            { time: hoursAgo(2), title: 'Run failed', description: 'Connection refused.', level: 'error' },
          ],
        },
        text: 'daily-report: last run failed (connection refused).',
      },
    ],
  },
  {
    level: 'info',
    content: [
      { type: 'text', text: 'Files found in the workspace:' },
      {
        type: 'widget',
        name: 'geenii.filetree',
        data: {
          root: '~/workspaces/geenii',
          expand: 1,
          entries: [
            { path: 'README.md', size: 4210 },
            { path: 'pyproject.toml', size: 1893 },
            { path: 'src/geenii/__init__.py', size: 0 },
            { path: 'src/geenii/config.py', size: 6120 },
            { path: 'src/geenii/chat_models.py', size: 5480 },
            { path: 'docs/developer-guide/messages.md', size: 9020 },
            { path: 'data/', type: 'dir' },
          ],
        },
        text: 'Workspace: README.md, pyproject.toml, src/, docs/, data/',
      },
    ],
  },
  {
    level: 'info',
    content: [
      { type: 'widget', name: 'geenii.unknown', title: 'Unknown widget', data: { any: 'thing' }, text: 'An *unknown* widget shows its fallback text.' },
    ],
  },
]

export const SAMPLE_MARKDOWN =`## Markdown text

This message shows the **text** renderer: *emphasis*, \`inline code\` and a [link](https://example.com).

- a bullet list
- with two items

1. and a numbered
2. list

> A blockquote.

GitHub-flavored markdown: ~~strikethrough~~, an autolink https://example.com and a task list:

- [x] render tables
- [ ] something left to do

| Part | Rendered as |
|---|---|
| text | markdown |
| tool_call | collapsible card |

\`\`\`python
def greet(name: str) -> str:
    return f"Hello, {name}!"
\`\`\`
`
