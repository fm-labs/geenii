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

/** Easter-egg (and dev) widget messages, keyed by the hidden echo command that sends them */
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
      heading: 'Snake',
      data: { size: 16, speed: 120 },
      text: '🐍 You found the snake. Try a client that supports widgets.',
    }],
  },
  fortune: {
    level: 'info',
    content: [{
      type: 'widget',
      name: 'geenii.fortune',
      heading: 'Fortune cookie',
      data: {},
      text: '🥠 It works on my machine.',
    }],
  },
  crash: {
    level: 'info',
    content: [{
      type: 'widget',
      name: 'geenii.dev.errorboundarytest',
      heading: 'Error boundary test',
      data: { delay: 3000, message: 'Crashed after 3 seconds, on purpose' },
      text: 'This widget crashed on purpose; the error boundary shows this fallback instead.',
    }],
  },
  dice: {
    level: 'info',
    content: [{
      type: 'widget',
      name: 'geenii.dice',
      heading: 'Dice',
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

/** Made-up daily activity for the last `days` days (deterministic: same pattern on every run), quieter on weekends */
const sampleActivity = (days: number) => Array.from({ length: days }, (_, i) => {
  const date = new Date(Date.now() - (days - 1 - i) * 86_400_000)
  const weekend = date.getUTCDay() === 0 || date.getUTCDay() === 6
  const noise = Math.abs(Math.sin(i * 12.9898) * 43758.5453) % 1
  return { date: date.toISOString().slice(0, 10), value: Math.floor(noise * (weekend ? 3 : 9)) }
})

/** A status history of `length` entries, 'up' except at the indexes in `bad`, which get `state` */
const sampleUptime = (length: number, bad: number[], state: 'degraded' | 'down' | 'maintenance' = 'down') =>
  Array.from({ length }, (_, i) => (bad.includes(i) ? state : 'up'))

/** ISO dates of the last `days` days, oldest first */
const daysAgo = (days: number) => Array.from({ length: days }, (_, i) => hoursAgo((days - 1 - i) * 24))

type SampleMessage = { level: SystemMessageLevel, content: ContentPart[] }

/** A group of samples, led by a small system text message with the group's title and widget names */
const group = (title: string, ...messages: SampleMessage[]): SampleMessage[] => {
  const names = [...new Set(messages.flatMap((m) => m.content)
    .flatMap((p) => (p.type === 'widget' ? [p.name.replace(/^geenii\./, '')] : [])))]
  return [{ level: 'info', content: [{ type: 'text', text: `**${title}**: ${names.join(', ')}` }] }, ...messages]
}

/**
 * System messages with one example per built-in widget (plus an unknown one, which shows its text),
 * as the server would send them. Built per call, since some data is relative to the current time.
 */
export const sampleWidgetMessages = (): SampleMessage[] => {
  const eggs = sampleEasterEggs()
  return [
    ...group('Data',
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
    ),
    ...group('Charts and numbers',
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
          {
            type: 'widget',
            name: 'geenii.donut',
            heading: 'Where did my tokens go?',
            data: {
              unit: 'k tokens',
              items: [
                { label: 'System prompt', value: 12.4 },
                { label: 'Tool results', value: 61.8 },
                { label: 'Conversation', value: 38.2 },
                { label: 'Skills', value: 9.6 },
                { label: 'Output', value: 21.5 },
              ],
            },
            text: 'Tokens: tool results 61.8k, conversation 38.2k, output 21.5k, system prompt 12.4k, skills 9.6k.',
          },
        ],
      },
      {
        level: 'warning',
        content: [
          { type: 'text', text: 'The context window is filling up.' },
          {
            type: 'widget',
            name: 'geenii.gauge',
            data: { value: 164, max: 200, unit: 'k', label: 'Context tokens used', thresholds: { warning: 140, error: 180 } },
            text: 'Context: 164k of 200k tokens used.',
          },
        ],
      },
      {
        level: 'info',
        content: [
          {
            type: 'widget',
            name: 'geenii.heatmap',
            heading: 'Chats per day',
            data: { unit: 'chats', weeks: 26, days: sampleActivity(26 * 7) },
            text: 'Chat activity over the last 26 weeks.',
          },
        ],
      },
      {
        level: 'info',
        content: [
          { type: 'text', text: 'Benchmark: cost vs. quality (bubble size = tokens per second):' },
          {
            type: 'widget',
            name: 'geenii.scatter',
            data: {
              x: { label: 'Cost', unit: '$ / M tokens' },
              y: { label: 'Score', unit: '%' },
              series: [
                {
                  name: 'hosted',
                  points: [
                    { x: 15, y: 91, label: 'opus', size: 60 },
                    { x: 3, y: 86, label: 'sonnet', size: 90 },
                    { x: 0.8, y: 74, label: 'haiku', size: 160 },
                  ],
                },
                {
                  name: 'local',
                  points: [
                    { x: 0.1, y: 62, label: 'llama3.2', size: 40 },
                    { x: 0.2, y: 68, label: 'qwen', size: 35 },
                  ],
                },
              ],
            },
            text: 'Benchmark: opus 91% ($15), sonnet 86% ($3), haiku 74% ($0.80), qwen 68%, llama3.2 62%.',
          },
        ],
      },
      {
        level: 'info',
        content: [
          {
            type: 'widget',
            name: 'geenii.funnel',
            heading: 'Agent runs this week',
            data: {
              unit: 'runs',
              steps: [
                { label: 'Started', value: 1240 },
                { label: 'Planned', value: 1180 },
                { label: 'Tools approved', value: 910 },
                { label: 'Completed', value: 842 },
                { label: 'Rated 👍', value: 515 },
              ],
            },
            text: 'Agent runs: 1240 started, 1180 planned, 910 tools approved, 842 completed, 515 rated 👍.',
          },
        ],
      },
      {
        level: 'info',
        content: [
          { type: 'text', text: 'Disk usage of the geenii data directory:' },
          {
            type: 'widget',
            name: 'geenii.treemap',
            data: {
              unit: 'MB',
              items: [
                {
                  label: 'models',
                  children: [
                    { label: 'llama3.2', value: 2020 },
                    { label: 'whisper-base', value: 142 },
                    { label: 'embeddings', value: 274 },
                  ],
                },
                {
                  label: 'conversations',
                  children: [{ label: '2026', value: 312 }, { label: '2025', value: 488 }, { label: 'attachments', value: 220 }],
                },
                { label: 'index', value: 640 },
                { label: 'logs', value: 96 },
                { label: 'cache', value: 58 },
              ],
            },
            text: 'Disk usage: models 2436 MB, conversations 1020 MB, index 640 MB, logs 96 MB, cache 58 MB.',
          },
        ],
      },
      {
        level: 'info',
        content: [
          {
            type: 'widget',
            name: 'geenii.sparklines',
            heading: 'Last 24 hours',
            data: {
              rows: [
                { label: 'Requests', description: 'per hour', values: [120, 98, 75, 60, 52, 80, 140, 210, 260, 280, 270, 300] },
                { label: 'Latency', description: 'p95', unit: 'ms', good: 'down', values: [910, 880, 860, 900, 1020, 940, 870, 820, 790, 760, 780, 740] },
                { label: 'Errors', unit: '%', good: 'down', values: [0.4, 0.3, 0.5, 0.2, 0.9, 1.6, 1.1, 0.6, 0.5, 0.6, 0.7, 0.8] },
                { label: 'Tokens', unit: 'k', values: [42, 40, 38, 36, 35, 39, 48, 55, 61, 58, 60, 59] },
              ],
            },
            text: 'Last 24 h: 300 requests/h (+150%), p95 latency 740 ms (−18.7%), errors 0.8% (+100%), 59k tokens.',
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
    ),
    ...group('Status and time',
      {
        level: 'warning',
        content: [
          {
            type: 'widget',
            name: 'geenii.status',
            heading: 'Services',
            data: {
              items: [
                { name: 'geenii server', status: 'up', uptime: 99.98, history: sampleUptime(40, []) },
                { name: 'Ollama', description: 'localhost:11434', status: 'up', uptime: 99.2, history: sampleUptime(40, [12, 13]) },
                {
                  name: 'MCP: whisper',
                  description: 'Slow responses since the last update',
                  status: 'degraded',
                  uptime: 97.5,
                  history: sampleUptime(40, [30, 37, 38, 39], 'degraded'),
                },
                { name: 'MCP: weather', status: 'down', url: 'https://example.com/status', uptime: 91.3, history: sampleUptime(40, [36, 37, 38, 39], 'down') },
                { name: 'Backups', status: 'maintenance', history: [...Array(30).fill(null), ...sampleUptime(10, [9], 'maintenance')] },
              ],
            },
            text: 'Services: geenii server up, Ollama up, MCP whisper degraded, MCP weather down, backups in maintenance.',
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
          { type: 'widget', name: 'geenii.progress', heading: 'Model download', data: { label: 'Downloading model llama3.2' }, text: 'Downloading model llama3.2…' },
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
          { type: 'text', text: 'Scheduled task **daily-report** runs at 18:00 UTC. Current time:' },
          { type: 'widget', name: 'geenii.clock', data: { timezone: 'UTC', label: 'UTC' }, text: 'Current time: see your clock (UTC).' },
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
          {
            type: 'widget',
            name: 'geenii.weather',
            data: {
              location: 'Vienna, Austria',
              current: { temp: 14.6, condition: 'Partly cloudy', feels_like: 13, humidity: 72, wind: 18 },
              // today and the next 4 days, as ISO dates (the widget shows weekday names)
              forecast: ['Partly cloudy', 'Light rain', 'Thunderstorms', 'Overcast', 'Sunny'].map((condition, i) => ({
                day: hoursAgo(-i * 24).slice(0, 10),
                condition,
                high: [16, 13, 15, 12, 18][i],
                low: [9, 8, 10, 7, 9][i],
                precip: [0, 80, 60, 10, 0][i],
              })),
            },
            text: 'Vienna: 15°C, partly cloudy. Next days: light rain, thunderstorms, overcast, sunny.',
          },
        ],
      },
    ),
    ...group('Code and files',
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
    ),
    ...group('Layout',
      {
        level: 'info',
        content: [
          {
            type: 'widget',
            name: 'geenii.tabs',
            heading: 'Session overview',
            data: {
              tabs: [
                {
                  label: 'Usage',
                  widget: {
                    name: 'geenii.stat',
                    data: { items: [{ label: 'Tokens', value: '143.5', unit: 'k', delta: 12 }, { label: 'Tool calls', value: 27 }, { label: 'Cost', value: '0.42', unit: '$' }] },
                  },
                },
                {
                  label: 'Tokens',
                  widget: {
                    name: 'geenii.donut',
                    data: { unit: 'k', items: [{ label: 'Input', value: 98.2 }, { label: 'Cache', value: 23.8 }, { label: 'Output', value: 21.5 }] },
                  },
                },
                {
                  label: 'Tools',
                  widget: {
                    name: 'geenii.table',
                    data: { columns: ['tool', 'calls', 'errors'], rows: [['read_file', 14, 0], ['shell', 9, 1], ['weather', 4, 0]] },
                  },
                },
                { label: 'Notes', text: 'Tabs can also hold **markdown**, and a tab whose widget is unknown shows that widget’s fallback text.' },
                { label: 'Unknown', widget: { name: 'acme.dashboard', text: 'The *acme.dashboard* widget is not installed here.' } },
              ],
            },
            text: 'Session overview: 143.5k tokens, 27 tool calls ($0.42). Tools: read_file 14, shell 9 (1 error), weather 4.',
          },
        ],
      },
    ),
    ...group('Embedded content and actions',
      {
        level: 'info',
        content: [
          { type: 'text', text: 'Web search results for **local-first ai agents**:' },
          {
            type: 'widget',
            name: 'geenii.links',
            data: {
              limit: 3,
              items: [
                { title: 'Local-first software: you own your data', url: 'https://www.inkandswitch.com/local-first/', snippet: 'Seven ideals for local-first software: no spinners, your work is not trapped on one device, the network is optional…' },
                { title: 'Ollama', url: 'https://ollama.com/', snippet: 'Get up and running with large language models, locally.' },
                { title: 'Model Context Protocol', url: 'https://modelcontextprotocol.io/introduction', snippet: 'An open protocol that standardizes how applications provide context to LLMs.' },
                { title: 'Example Domain', url: 'https://example.com/', source: 'example.com', snippet: 'This domain is for use in illustrative examples in documents.' },
                { title: 'Not a web link', url: 'javascript:alert(1)', snippet: 'Unsafe urls are shown without a link.' },
              ],
            },
            text: 'Results: inkandswitch.com/local-first, ollama.com, modelcontextprotocol.io, example.com',
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
          { type: 'text', text: 'The agent prepared a webhook call. Send it?' },
          {
            type: 'widget',
            name: 'geenii.postbutton',
            data: { url: 'https://httpbin.org/post', payload: { event: 'deploy', env: 'staging' }, label: 'Trigger deploy', confirm: 'Deploy to staging?' },
            text: 'Webhook: POST https://httpbin.org/post {"event": "deploy", "env": "staging"}',
          },
        ],
      },
      {
        level: 'warning',
        content: [
          { type: 'text', text: 'A webhook that answers 500, to show the failed state:' },
          {
            type: 'widget',
            name: 'geenii.postbutton',
            data: { url: 'https://httpbin.org/status/500', payload: { ping: true }, label: 'Ping' },
            text: 'Webhook: POST https://httpbin.org/status/500',
          },
        ],
      },
    ),
    ...group('Replies',
      {
        level: 'info',
        content: [
          { type: 'text', text: 'The build passed. How do you want to continue?' },
          {
            type: 'widget',
            name: 'geenii.choices',
            data: {
              options: [
                { label: 'Deploy to staging', message: 'Yes, deploy the build to staging.' },
                { label: 'Show the diff first', message: 'Show me the diff first.' },
                'Cancel',
              ],
            },
            text: 'Reply with: "Deploy to staging", "Show the diff first" or "Cancel".',
          },
        ],
      },
      {
        level: 'info',
        content: [
          { type: 'text', text: 'To create the scheduled task, I need a few details:' },
          {
            type: 'widget',
            name: 'geenii.form',
            heading: 'New scheduled task',
            data: {
              submit: 'Create task',
              fields: [
                { name: 'name', label: 'Name', required: true, placeholder: 'daily-report' },
                { name: 'schedule', label: 'Schedule', type: 'select', required: true, options: ['hourly', 'daily', 'weekly'], default: 'daily' },
                { name: 'time', label: 'Time (UTC)', placeholder: '18:00' },
                { name: 'retries', label: 'Retries', type: 'number', default: 2 },
                { name: 'notify', label: 'Notify me on failure', type: 'checkbox', default: true },
                { name: 'prompt', label: 'Prompt', type: 'textarea', placeholder: 'Summarize yesterday’s activity…' },
              ],
            },
            text: 'Please reply with the task name, schedule (hourly, daily or weekly), time, retries, whether to notify on failure, and the prompt.',
          },
        ],
      },
      {
        level: 'info',
        content: [
          { type: 'text', text: 'Task done. How did I do?' },
          {
            type: 'widget',
            name: 'geenii.rating',
            data: { type: 'stars', comment: true },
            text: 'Rate the answer from 1 to 5, optionally with a comment.',
          },
        ],
      },
      {
        level: 'info',
        content: [
          {
            type: 'widget',
            name: 'geenii.rating',
            heading: 'Was this answer helpful?',
            data: { type: 'thumbs' },
            text: 'Was this answer helpful? Reply with yes or no.',
          },
        ],
      },
    ),
    ...group('Easter eggs', eggs.matrix, eggs.boot, eggs.snake, eggs.fortune, eggs.dice),
    ...group('Development aids',
      {
        level: 'info',
        content: [
          {
            type: 'widget',
            name: 'geenii.dev.errorboundarytest',
            heading: 'Error boundary test',
            data: { message: 'Crashed on purpose' },
            text: 'This widget crashed on purpose; the error boundary shows this fallback instead.',
          },
        ],
      },
      eggs.crash,
      {
        level: 'info',
        content: [
          { type: 'widget', name: 'geenii.unknown', heading: 'Unknown widget', data: { any: 'thing' }, text: 'An *unknown* widget shows its fallback text.' },
        ],
      },
    ),
  ]
}

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
