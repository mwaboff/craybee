/**
 * Pure contract mirror of backend/schemas/llm_server.py and backend/models/llm_server.py.
 * No behavior here -- keep this file free of imports/logic beyond the constants below.
 */

export type ProviderKind = "openai_compatible" | "anthropic" | "claude_cli";

export type Capabilities = {
  supports_tools: boolean;
  supports_vision: boolean;
  supports_streaming: boolean;
  supports_structured_output: boolean;
};

export type LLMServer = Capabilities & {
  id: string;
  name: string;
  provider: ProviderKind;
  base_url: string | null;
  has_api_key: boolean;
  executable_path: string | null;
  default_model: string | null;
  options: Record<string, unknown>;
  is_default: boolean;
  is_enabled: boolean;
  created_at: string;
  updated_at: string;
};

export type LLMServerCreate = Partial<Capabilities> & {
  name: string;
  provider: ProviderKind;
  base_url?: string | null;
  api_key?: string | null;
  executable_path?: string | null;
  default_model?: string | null;
  options?: Record<string, unknown>;
  is_enabled?: boolean;
  is_default?: boolean;
};

/** Partial update; only present keys are applied. `api_key: null` clears the key, omitting keeps it. */
export type LLMServerUpdate = Partial<Omit<LLMServerCreate, "is_default">>;

export type ModelList = { models: string[] };

export type ServerFieldName = "name" | "base_url" | "api_key" | "executable_path" | "default_model";

export const SERVER_FIELD_NAMES: readonly ServerFieldName[] = [
  "name",
  "base_url",
  "api_key",
  "executable_path",
  "default_model",
];

export type OptionFieldName = "system_prompt" | "max_tokens";

export type ProviderMeta = {
  label: string;
  fields: ServerFieldName[];
  required: ServerFieldName[];
  capabilityDefaults: Capabilities;
  optionFields: OptionFieldName[];
};

// Mirrors CAPABILITY_DEFAULTS and check_provider_rules in backend/schemas/llm_server.py.
export const PROVIDER_META: Record<ProviderKind, ProviderMeta> = {
  openai_compatible: {
    label: "OpenAI-compatible",
    fields: ["base_url", "api_key"],
    required: ["base_url"],
    capabilityDefaults: {
      supports_tools: false,
      supports_vision: false,
      supports_streaming: true,
      supports_structured_output: false,
    },
    optionFields: ["system_prompt"],
  },
  anthropic: {
    label: "Anthropic",
    fields: ["api_key"],
    required: ["api_key"],
    capabilityDefaults: {
      supports_tools: true,
      supports_vision: true,
      supports_streaming: true,
      supports_structured_output: true,
    },
    optionFields: ["system_prompt", "max_tokens"],
  },
  claude_cli: {
    label: "Claude CLI",
    fields: ["executable_path"],
    required: [],
    capabilityDefaults: {
      supports_tools: true,
      supports_vision: true,
      supports_streaming: true,
      supports_structured_output: false,
    },
    optionFields: ["system_prompt"],
  },
};
