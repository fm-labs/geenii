/** The url if it is http(s), else null (no javascript:, data:, file: …); relative urls resolve against the page */
export const safeUrl = (url?: string): URL | null => {
  try {
    const parsed = new URL(url ?? '', window.location.href)
    return parsed.protocol === 'http:' || parsed.protocol === 'https:' ? parsed : null
  } catch {
    return null
  }
}
