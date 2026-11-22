import { RJSFSchema } from '@rjsf/utils'
import Form from '@rjsf/shadcn'
import validator from '@rjsf/validator-ajv8'
import { Button } from '@/components/ui/button.tsx'
import * as React from 'react'
import { useApi } from '@/context/api-context.tsx'

/**
 * A user settings form, loaded from and saved to its NAMESPACE of the
 * `userSettings` section in the user's settings.json.
 */
export const SettingsFormView = ({ namespace, schema, uiSchema, onSaved }: {
  namespace: string,
  schema: RJSFSchema,
  uiSchema?: any,
  /** called with the values once they're saved */
  onSaved?: (values: Record<string, any>) => void,
}) => {
  const { fetchJson } = useApi()
  const url = `/api/v1/settings/user/${encodeURIComponent(namespace)}`

  const [formData, setFormData] = React.useState<Record<string, any>>()
  const [loadError, setLoadError] = React.useState<string | null>(null)
  const [saving, setSaving] = React.useState(false)
  const [saved, setSaved] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  React.useEffect(() => {
    let cancelled = false
    setFormData(undefined)
    setLoadError(null)
    ;(fetchJson(url) as Promise<Record<string, any>>)
      .then((data) => { if (!cancelled) setFormData(data) })
      .catch((err) => { if (!cancelled) setLoadError(err?.message || 'Unknown error') })
    return () => { cancelled = true }
  }, [fetchJson, url])

  const handleSubmit = async ({ formData: data }: any) => {
    setSaving(true)
    setError(null)
    try {
      const savedValues = await fetchJson(url, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data ?? {}),
      })
      setFormData(savedValues)
      onSaved?.(savedValues)
      setSaved(true)
      setTimeout(() => setSaved(false), 1500)
    } catch (err: any) {
      setError(err?.message || String(err))
    } finally {
      setSaving(false)
    }
  }

  if (loadError) {
    return <p className={'text-destructive'}>Failed to load settings: {loadError}</p>
  }
  if (formData === undefined) {
    return <p className={'text-muted-foreground'}>Loading settings…</p>
  }

  return (
    <Form
      schema={schema}
      uiSchema={uiSchema}
      validator={validator}
      formData={formData}
      onChange={({ formData: data }) => setFormData(data)}
      onSubmit={handleSubmit}
      disabled={saving}
    >
      <div className={'py-4 flex items-center justify-end gap-3'}>
        {error && <span className={'text-sm text-destructive'}>{error}</span>}
        {saved && <span className={'text-sm text-muted-foreground'}>Saved</span>}
        <Button type={'submit'} disabled={saving}>{saving ? 'Saving…' : 'Save'}</Button>
      </div>
    </Form>
  )
}
