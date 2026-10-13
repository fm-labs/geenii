import { RJSFSchema } from '@rjsf/utils'

/** Tool definition as returned by GET /api/v1/tools/ */
export type ToolType = {
  name: string;
  type: string;
  description?: string | null;
  parameters?: RJSFSchema;
}
