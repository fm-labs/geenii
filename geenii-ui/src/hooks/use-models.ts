import React from 'react'
import { useApi } from '@/context/api-context.tsx'
import { AiModelInfo } from '@/api/xai.types.ts'

/** Model id as expected by the completion APIs: "provider:name" */
export const modelId = (model: AiModelInfo) => `${model.provider}:${model.name}`

// One request per server: enumerating models queries every provider, and several selectors share the list.
const cache = new Map<string, Promise<AiModelInfo[]>>()

/**
 * The models available on the server (GET /api/v1/ai/models).
 * Failed requests are not cached; `reload()` fetches the list again.
 * With `enabled: false` nothing is fetched.
 */
export const useModels = ({ enabled = true }: { enabled?: boolean } = {}) => {
  const { apiBaseUrl, fetchJson } = useApi()
  const [models, setModels] = React.useState<AiModelInfo[]>([])
  const [loading, setLoading] = React.useState<boolean>(true)
  const [error, setError] = React.useState<string | null>(null)
  const [reloadCount, setReloadCount] = React.useState(0)

  React.useEffect(() => {
    if (!enabled) {
      setLoading(false)
      return
    }
    let request = cache.get(apiBaseUrl)
    if (!request) {
      request = fetchJson('/api/v1/ai/models') as Promise<AiModelInfo[]>
      cache.set(apiBaseUrl, request)
      request.catch(() => cache.delete(apiBaseUrl))
    }

    let active = true
    setLoading(true)
    setError(null)
    request
      .then((data) => active && setModels(data))
      .catch((err) => {
        console.error('Error fetching models', err)
        if (active) setError(err?.message || 'Unknown error')
      })
      .finally(() => active && setLoading(false))
    return () => {
      active = false
    }
  }, [enabled, apiBaseUrl, fetchJson, reloadCount])

  const reload = React.useCallback(() => {
    cache.delete(apiBaseUrl)
    setReloadCount((c) => c + 1)
  }, [apiBaseUrl])

  return { models, loading, error, reload }
}
