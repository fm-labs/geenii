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

/** APPEARANCE SETTINGS **/
const appearanceSettingsSchema: RJSFSchema = {
  title: "Appearance Settings",
  type: "object",
  properties: {
    theme: {
      type: "string",
      title: "Theme",
      enum: ["light", "dark", "system"],
      default: "system",
    },
    fontFamily: {
      type: "string",
      title: "Font Family",
      enum: ["system", "sans-serif", "serif", "monospace"],
      default: "system",
    },
    fontSize: {
      type: "number",
      title: "Font Size",
      minimum: 10,
      maximum: 24,
      default: 14,
    },
  },
};

const appearanceSettingsUiSchema = {
  theme: {
    "ui:widget": "select",
  },
  fontFamily: {
    "ui:widget": "select",
    "ui:options": {
      enumOptions: [
        { value: "system", label: "System Default" },
        { value: "sans-serif", label: "Sans Serif" },
        { value: "serif", label: "Serif" },
        { value: "monospace", label: "Monospace" },
      ],
    },
  },
  fontSize: {
    "ui:widget": "range",
    "ui:options": {
      step: 1,
      minimum: 10,
      maximum: 24
    },
  },
};


export const settingsForms = {
  "appearance": [appearanceSettingsSchema, appearanceSettingsUiSchema],
  "profile": [profileSettingsSchema, profileSettingsUiSchema],
  "default_models": [aiModelSettingsSchema, aiModelSettingsUiSchema],
}