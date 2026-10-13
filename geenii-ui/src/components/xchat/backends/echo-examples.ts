// Offline sample data for the echo backend's "example" turn (data URLs, so nothing is fetched).

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

export const SAMPLE_MARKDOWN = `## Markdown text

This message shows the **text** renderer: *emphasis*, \`inline code\` and a [link](https://example.com).

- a bullet list
- with two items

1. and a numbered
2. list

> A blockquote.

\`\`\`python
def greet(name: str) -> str:
    return f"Hello, {name}!"
\`\`\`
`
