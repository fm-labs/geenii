import { RJSFSchema } from '@rjsf/utils'

/** PROFILE SETTINGS **/
const profileSettingsSchema: RJSFSchema = {
  title: "Settings",
  type: "object",
  properties: {
    username: { type: "string", title: "Username" },
    email: { type: "string", title: "Email" },
    notifications: {
      type: "boolean",
      title: "Enable Notifications",
      default: true,
    },
  },
};

const profileSettingsUiSchema = {
  email: {
    "ui:widget": "email",
    "ui:placeholder": "",
  },
  notifications: {
    "ui:widget": "checkbox",
  },
};

/** AI MODEL PREFERENCES **/
const aiModelSettingsSchema: RJSFSchema = {
  title: "AI Model Preferences",
  type: "object",
  properties: {
    defaultModel: {
      type: "string",
      title: "Default AI Model",
      enum: ["ollama:mistral:latest", "openai:gpt-3.5-turbo", "openai:gpt-4", "openai:gpt-4o-mini"],
      default: "ollama:mistral:latest",
    },
    temperature: {
      type: "number",
      title: "Response Temperature",
      minimum: 0,
      maximum: 1,
      default: 0.7,
    },
  },
};

const aiModelSettingsUiSchema = {
  defaultModel: {
    "ui:widget": "select",
  },
  // temperature: {
  //   "ui:widget": "range",
  //   "ui:options": {
  //     step: 0.1,
  //   },
  // },
};


export const settingsForms = {
  "profile": [profileSettingsSchema, profileSettingsUiSchema],
  "default_models": [aiModelSettingsSchema, aiModelSettingsUiSchema],
}