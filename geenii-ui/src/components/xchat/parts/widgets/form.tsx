import React from 'react'
import { CheckIcon, SendIcon } from 'lucide-react'
import { Button } from '@/components/ui/button.tsx'
import { Input } from '@/components/ui/input.tsx'
import { Label } from '@/components/ui/label.tsx'
import { Textarea } from '@/components/ui/textarea.tsx'
import { WidgetRendererProps } from '@/components/xchat/chat.types.ts'
import { useChatReply } from './use-chat-reply.ts'

type FieldType = 'text' | 'textarea' | 'number' | 'select' | 'checkbox' | 'date' | 'email' | 'url'

type Field = {
  name: string
  label?: string
  type?: FieldType
  required?: boolean
  options?: string[]
  default?: string | number | boolean
  placeholder?: string
}

type FormWidgetData = { fields: Field[]; submit?: string; format?: 'text' | 'json'; once?: boolean }

type Values = Record<string, string | number | boolean | null>

const selectClass = 'h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 dark:bg-input/30'

const initialValue = (field: Field): string | boolean =>
  field.type === 'checkbox' ? field.default === true : field.default != null ? String(field.default) : ''

/** The values as the user message: "Label: value" lines, or a JSON code block */
export const formMessage = (fields: Field[], values: Values, format: 'text' | 'json') => {
  if (format === 'json') return '```json\n' + JSON.stringify(values, null, 2) + '\n```'
  return fields
    .filter((f) => values[f.name] !== null && values[f.name] !== '')
    .map((f) => `${f.label || f.name}: ${f.type === 'checkbox' ? (values[f.name] ? 'yes' : 'no') : values[f.name]}`)
    .join('\n')
}

/**
 * geenii.form — data: { fields: { name, label?, type? = text, required?, options?, default?, placeholder? }[],
 *   submit? = 'Send', format? = 'text' | 'json', once? = true }
 * Submits the values as one user message. Types: text, textarea, number, select (options), checkbox, date, email, url.
 */
export const FormWidget = ({ data, message }: WidgetRendererProps<FormWidgetData | null>) => {
  const fields = (Array.isArray(data?.fields) ? data.fields : []).filter((f): f is Field => typeof f?.name === 'string')
  const [values, setValues] = React.useState<Record<string, string | boolean>>(
    () => Object.fromEntries(fields.map((f) => [f.name, initialValue(f)])))
  const { reply, busy, answer, error } = useChatReply(message)
  const [submitted, setSubmitted] = React.useState(false)
  const locked = (data?.once ?? true) && (submitted || answer != null)
  const id = React.useId()

  const set = (name: string, value: string | boolean) => setValues((v) => ({ ...v, [name]: value }))

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    // numbers as numbers, empty optional fields as null
    const typed: Values = Object.fromEntries(fields.map((f) => {
      const v = values[f.name]
      if (f.type === 'checkbox') return [f.name, v === true]
      if (v === '') return [f.name, null]
      return [f.name, f.type === 'number' ? Number(v) : v as string]
    }))
    if (await reply(formMessage(fields, typed, data?.format ?? 'text'))) setSubmitted(true)
  }

  return (
    <form onSubmit={onSubmit} className={'max-w-md rounded-md border p-3'}>
      <fieldset disabled={busy || locked} className={'flex flex-col gap-3'}>
        {fields.map((field) => {
          const fieldId = `${id}-${field.name}`
          const label = field.label || field.name
          const common = { id: fieldId, name: field.name, required: field.required, placeholder: field.placeholder }
          if (field.type === 'checkbox') {
            return (
              <label key={field.name} htmlFor={fieldId} className={'flex items-center gap-2 text-sm'}>
                <input type={'checkbox'} {...common} checked={values[field.name] === true}
                       onChange={(e) => set(field.name, e.target.checked)} className={'size-4'} />
                {label}
              </label>
            )
          }
          const value = String(values[field.name] ?? '')
          const onChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
            set(field.name, e.target.value)
          return (
            <div key={field.name} className={'flex flex-col gap-1.5'}>
              <Label htmlFor={fieldId}>{label}{field.required && <span className={'text-destructive'}>*</span>}</Label>
              {field.type === 'textarea' ? <Textarea {...common} value={value} onChange={onChange} />
                : field.type === 'select' ? (
                  <select {...common} value={value} onChange={onChange} className={selectClass}>
                    {!field.required && <option value={''}>—</option>}
                    {field.required && value === '' && <option value={''} disabled>Choose…</option>}
                    {(field.options ?? []).map((o) => <option key={o} value={o}>{o}</option>)}
                  </select>
                )
                  : <Input {...common} type={field.type ?? 'text'} value={value} onChange={onChange} />}
            </div>
          )
        })}
        <div className={'flex items-center gap-2'}>
          <Button type={'submit'} size={'sm'} variant={locked ? 'outline' : 'default'}>
            {locked ? <CheckIcon /> : <SendIcon />}
            {locked ? 'Sent' : data?.submit || 'Send'}
          </Button>
          {error && <span className={'text-xs text-destructive'}>{error}</span>}
        </div>
      </fieldset>
    </form>
  )
}
