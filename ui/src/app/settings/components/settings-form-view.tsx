import { RJSFSchema } from '@rjsf/utils'
import Form from '@rjsf/shadcn'
import validator from '@rjsf/validator-ajv8'
import { Button } from '@/components/ui/button.tsx'
import * as React from 'react'

export const SettingsFormView = ({ schema, uiSchema }: { schema: RJSFSchema, uiSchema?: any }) => {

  const handleSubmit = ({ formData }: any) => {
    console.warn('(missing form handler) Settings Form data submitted: ', formData)
  }

  return (
    <Form
      schema={schema}
      uiSchema={uiSchema}
      validator={validator}
      onSubmit={handleSubmit}
    ></Form>
  )
}