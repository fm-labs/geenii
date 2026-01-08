import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { RJSFSchema } from '@rjsf/utils'
import Form from '@rjsf/shadcn'
import validator from '@rjsf/validator-ajv8'


type SchemaFormProps = {
  schema: RJSFSchema,
  uiSchema?: any,
  onSubmit?: (data: any) => Promise<void>
  onChange?: (data: any) => Promise<void>
  submitButtonText?: string
}

type SchemaFormDialogProps = SchemaFormProps & {
  open: boolean
  onOpenChange: (open: boolean) => void
  dialogTitle?: string
  dialogDescription?: string
  dialogTriggerShow?: boolean
  dialogTriggerButtonText?: string
}

export function SchemaFormDialog(props: SchemaFormDialogProps) {

  const handleSubmit = async (data: any) => {
    // Handle form submission
    console.log("Form submitted with data:", data.formData);
    if (props?.onSubmit) {
      await props.onSubmit(data)
    }
  }

  const handleChange = async (data: any) => {
    // Handle form data change
    console.log("Form data changed:", data.formData);
    if (props?.onChange) {
      await props.onChange(data)
    }
  }

  return (
    <Dialog open={props.open} onOpenChange={props.onOpenChange}>
      {props?.dialogTriggerShow && <DialogTrigger asChild>
          <Button variant="outline">{props?.dialogTriggerButtonText || 'Open'}</Button>
        </DialogTrigger>}
        <DialogContent className="sm:max-w-[525px]">
          <DialogHeader>
            {props?.dialogTitle && <DialogTitle>{props.dialogTitle}</DialogTitle>}
            {props?.dialogDescription && <DialogDescription>
              Make changes to your profile here. Click save when you&apos;re
              done.
            </DialogDescription>}
          </DialogHeader>
          <Form schema={props.schema}
                uiSchema={props?.uiSchema}
                onSubmit={handleSubmit}
                onChange={handleChange}
                validator={validator}
          >
            <DialogFooter className={"mt-6"}>
              <DialogClose asChild>
                <Button variant="outline">Cancel</Button>
              </DialogClose>
              <Button type="submit">{props?.submitButtonText || 'Submit'}</Button>
            </DialogFooter>
          </Form>
        </DialogContent>
    </Dialog>
  )
}
