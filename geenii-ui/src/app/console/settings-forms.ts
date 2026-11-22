import { RJSFSchema } from '@rjsf/utils'
import { COLOR_SCHEMES, DEFAULT_COLOR_SCHEME } from '@/components/color-schemes.ts'
import ColorSchemeWidget from '@/app/console/components/color-scheme-widget.tsx'

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
    colorScheme: {
      type: "string",
      title: "Color Scheme",
      enum: COLOR_SCHEMES.map((s) => s.value),
      default: DEFAULT_COLOR_SCHEME,
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
      default: 16,
    },
  },
};

const appearanceSettingsUiSchema = {
  theme: {
    "ui:widget": "select",
  },
  colorScheme: {
    "ui:widget": ColorSchemeWidget,
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

/** AUDIO SETTINGS **/
const audioSettingsSchema: RJSFSchema = {
  title: "Audio Settings",
  type: "object",
  properties: {
    echoCancellation: { type: "boolean", title: "Echo Cancellation", default: true },
    noiseSuppression: { type: "boolean", title: "Noise Suppression", default: true },
    autoGainControl: { type: "boolean", title: "Automatic Gain Control", default: true },
  },
};

const audioSettingsUiSchema = {
  echoCancellation: { "ui:widget": "checkbox" },
  noiseSuppression: { "ui:widget": "checkbox" },
  autoGainControl: { "ui:widget": "checkbox" },
};


export const settingsForms = {
  "appearance": [appearanceSettingsSchema, appearanceSettingsUiSchema],
  "profile": [profileSettingsSchema, profileSettingsUiSchema],
  "audio": [audioSettingsSchema, audioSettingsUiSchema],
  "default_models": [aiModelSettingsSchema, aiModelSettingsUiSchema],
}