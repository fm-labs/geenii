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
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { RJSFSchema } from '@rjsf/utils'
import Form from '@rjsf/shadcn'
import validator from '@rjsf/validator-ajv8'
import { SchemaFormDialog } from '@/components/form/schema-form-dialog.tsx'
import { toast } from 'react-toastify'
import { FormEvent } from 'react'
import { XAI_API_URL } from '@/constants.ts'

type NewAssistantProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
}


const newAssistantSchema: RJSFSchema = {
  title: "New Assistant",
  type: "object",
  required: ["name", "description"],
  properties: {
    name: {
      type: "string",
      title: "Assistant Name",
      default: "",
    },
    description: {
      type: "string",
      title: "Description",
      default: "",
    },
    model: {
      type: "string",
      title: "Model",
      enum: ["gpt-3.5-turbo", "gpt-4", "custom-model"],
      default: "gpt-3.5-turbo",
    },
    temperature: {
      type: "number",
      title: "Temperature",
      default: 0.7,
      minimum: 0,
      maximum: 1,
    },
    systemPrompt: {
      type: "string",
      title: "System Prompt",
      default: "You are a helpful assistant.",
    },
  },
}

const newAssistantUiSchema = {
  description: {
    "ui:widget": "textarea",
    "ui:options": {
      rows: 3,
    },
  },
  systemPrompt: {
    "ui:widget": "textarea",
    "ui:options": {
      rows: 5,
    },
  }
}

export function NewAssistantDialogButton({open, onOpenChange}: NewAssistantProps) {

  const onFormSubmit = async (data: any) => {
    console.log("New Assistant Data:", data.formData);
    // Add logic to create a new assistant with the provided data

    try {
      const response = await fetch(XAI_API_URL + 'ai/v1/assistants', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(data.formData),
      });

      if (!response.ok) {
        throw new Error(`Error creating assistant: ${response.statusText}`);
      }

      const result = await response.json();
      console.log("Assistant created successfully:", result);
      //onOpenChange(false);
    } catch (error) {
      console.error("Failed to create assistant:", error);
      toast.error(error.message);
    } finally {
      //onOpenChange(false);
    }
  }

  return (
    <SchemaFormDialog schema={newAssistantSchema}
                      uiSchema={newAssistantUiSchema}
                      dialogTitle="Create New Assistant"
                      dialogDescription="Fill out the form below to create a new assistant."
                      dialogTriggerButtonText="Create Assistant"
                      dialogTriggerShow={true}
                      open={open}
                      onOpenChange={onOpenChange}
                      onSubmit={onFormSubmit} />
  )
}

