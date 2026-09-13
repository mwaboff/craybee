import { ApiError } from "@/api/client";
import { SERVER_FIELD_NAMES, type OptionFieldName, type ServerFieldName } from "@/features/settings/types";

export type FormErrors = {
  form?: string;
  fields: Partial<Record<ServerFieldName | OptionFieldName, string>>;
};

// Matches a model-validator/rule message naming the field it applies to, e.g.
// "Value error, base_url is required for openai_compatible servers" or
// "api_key is required for anthropic servers".
const FIELD_MESSAGE_RE = /^(?:Value error, )?(name|base_url|api_key|executable_path|default_model)\b/;

export function toFormErrors(error: unknown): FormErrors {
  if (error instanceof ApiError) {
    const fields: Partial<Record<ServerFieldName, string>> = {};
    for (const key of SERVER_FIELD_NAMES) {
      const message = error.fieldErrors[key];
      if (message) fields[key] = message;
    }

    // Per-field messages from fieldErrors take priority: if any came through,
    // don't also surface a redundant form-level banner.
    if (Object.keys(fields).length > 0) {
      return { fields };
    }

    const message = error.message;
    const match = message.match(FIELD_MESSAGE_RE);
    const field = match?.[1] as ServerFieldName | undefined;

    if (field) {
      fields[field] = message.replace(/^Value error, /, "");
      return { fields };
    }
    if (message) {
      return { form: message, fields };
    }
    return { fields };
  }

  return { form: "Something went wrong. Please try again.", fields: {} };
}
