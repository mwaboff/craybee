import { PlugZap, Trash2, Undo2 } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";

import { Alert } from "@/components/ui/Alert";
import { FormField, inputClassName } from "@/components/ui/FormField";
import { HexLoader } from "@/components/ui/HexLoader";
import { IconButton } from "@/components/ui/IconButton";
import { toFormErrors, type FormErrors } from "@/features/settings/formErrors";
import {
  useCreateLlmServer,
  useDeleteLlmServer,
  useSetDefaultLlmServer,
  useTestConnection,
  useUpdateLlmServer,
} from "@/features/settings/hooks/useLlmServers";
import {
  PROVIDER_META,
  type Capabilities,
  type LLMServer,
  type LLMServerCreate,
  type LLMServerUpdate,
  type OptionFieldName,
  type ProviderKind,
  type ServerFieldName,
} from "@/features/settings/types";

import styles from "./LlmServerForm.module.css";

type FormValues = {
  name: string;
  provider: ProviderKind;
  base_url: string;
  api_key: string;
  executable_path: string;
  default_model: string;
  system_prompt: string;
  max_tokens: string;
  is_enabled: boolean;
  is_default: boolean;
} & Capabilities;

type Props = {
  server: LLMServer | null;
  currentDefaultName?: string;
  onCreated: (server: LLMServer) => void;
  onDeleted: () => void;
  onDirtyChange: (dirty: boolean) => void;
};

const FIELD_LABELS: Record<ServerFieldName, string> = {
  name: "Name",
  base_url: "Base URL",
  api_key: "API key",
  executable_path: "Executable path",
  default_model: "Default model",
};

const CAPABILITY_FIELDS: { key: keyof Capabilities; label: string }[] = [
  { key: "supports_tools", label: "Tools" },
  { key: "supports_vision", label: "Vision" },
  { key: "supports_streaming", label: "Streaming" },
  { key: "supports_structured_output", label: "Structured output" },
];

export function toFormValues(server: LLMServer | null): FormValues {
  if (!server) {
    return {
      name: "",
      provider: "openai_compatible",
      base_url: "",
      api_key: "",
      executable_path: "",
      default_model: "",
      system_prompt: "",
      max_tokens: "",
      is_enabled: true,
      is_default: false,
      ...PROVIDER_META.openai_compatible.capabilityDefaults,
    };
  }
  return {
    name: server.name,
    provider: server.provider,
    base_url: server.base_url ?? "",
    api_key: "",
    executable_path: server.executable_path ?? "",
    default_model: server.default_model ?? "",
    system_prompt: typeof server.options.system_prompt === "string" ? server.options.system_prompt : "",
    max_tokens: typeof server.options.max_tokens === "number" ? String(server.options.max_tokens) : "",
    is_enabled: server.is_enabled,
    is_default: server.is_default,
    supports_tools: server.supports_tools,
    supports_vision: server.supports_vision,
    supports_streaming: server.supports_streaming,
    supports_structured_output: server.supports_structured_output,
  };
}

function shallowEqual(a: FormValues, b: FormValues): boolean {
  return (Object.keys(a) as (keyof FormValues)[]).every((key) => a[key] === b[key]);
}

/**
 * Copies `base`, then sets or deletes each option key the current provider owns
 * (`system_prompt`, `max_tokens`) from the form values. Keys the form does not
 * own (`request`, `extra_args`, `cwd`) survive untouched.
 */
export function buildOptions(values: FormValues, base: Record<string, unknown>): Record<string, unknown> {
  const options: Record<string, unknown> = { ...base };
  const meta = PROVIDER_META[values.provider];

  if (meta.optionFields.includes("system_prompt")) {
    if (values.system_prompt.trim()) {
      options.system_prompt = values.system_prompt.trim();
    } else {
      delete options.system_prompt;
    }
  }

  if (meta.optionFields.includes("max_tokens")) {
    if (values.max_tokens.trim()) {
      options.max_tokens = Number(values.max_tokens);
    } else {
      delete options.max_tokens;
    }
  }

  return options;
}

export function toCreateBody(values: FormValues): LLMServerCreate {
  const meta = PROVIDER_META[values.provider];
  const body: LLMServerCreate = {
    name: values.name.trim(),
    provider: values.provider,
    is_enabled: values.is_enabled,
    is_default: values.is_default,
    supports_tools: values.supports_tools,
    supports_vision: values.supports_vision,
    supports_streaming: values.supports_streaming,
    supports_structured_output: values.supports_structured_output,
    options: buildOptions(values, {}),
  };
  if (values.default_model.trim()) body.default_model = values.default_model.trim();
  if (meta.fields.includes("base_url") && values.base_url.trim()) {
    body.base_url = values.base_url.trim();
  }
  if (meta.fields.includes("api_key") && values.api_key.trim()) {
    body.api_key = values.api_key.trim();
  }
  if (meta.fields.includes("executable_path") && values.executable_path.trim()) {
    body.executable_path = values.executable_path.trim();
  }
  return body;
}

export function toUpdateBody(
  values: FormValues,
  initial: FormValues,
  clearApiKey: boolean,
  server: LLMServer,
): LLMServerUpdate {
  const body: LLMServerUpdate = {};
  const meta = PROVIDER_META[values.provider];

  if (values.name !== initial.name) body.name = values.name.trim();
  const providerChanged = values.provider !== initial.provider;
  if (providerChanged) body.provider = values.provider;

  if (meta.fields.includes("base_url") && values.base_url !== initial.base_url) {
    body.base_url = values.base_url.trim() ? values.base_url.trim() : null;
  }
  if (meta.fields.includes("executable_path") && values.executable_path !== initial.executable_path) {
    body.executable_path = values.executable_path.trim() ? values.executable_path.trim() : null;
  }
  if (values.default_model !== initial.default_model) {
    body.default_model = values.default_model.trim() ? values.default_model.trim() : null;
  }

  if (
    providerChanged ||
    values.system_prompt !== initial.system_prompt ||
    values.max_tokens !== initial.max_tokens
  ) {
    body.options = buildOptions(values, providerChanged ? {} : server.options);
  }

  if (clearApiKey) {
    body.api_key = null;
  } else if (meta.fields.includes("api_key") && values.api_key.trim()) {
    body.api_key = values.api_key.trim();
  }

  if (values.is_enabled !== initial.is_enabled) body.is_enabled = values.is_enabled;

  for (const { key } of CAPABILITY_FIELDS) {
    if (values[key] !== initial[key]) body[key] = values[key];
  }

  return body;
}

export function validate(
  values: FormValues,
  server: LLMServer | null,
  clearApiKey: boolean,
): FormErrors["fields"] {
  const fields: FormErrors["fields"] = {};
  if (!values.name.trim()) fields.name = "Name is required.";

  const meta = PROVIDER_META[values.provider];
  for (const field of meta.required) {
    if (field === "api_key" && server?.has_api_key && !clearApiKey) continue;
    const value = field === "name" ? values.name : (values[field] as string);
    if (!value.trim()) fields[field] = `${FIELD_LABELS[field]} is required.`;
  }

  if (meta.optionFields.includes("max_tokens") && values.max_tokens.trim()) {
    const parsed = Number(values.max_tokens);
    if (!Number.isInteger(parsed) || parsed <= 0) {
      fields.max_tokens = "Must be a positive whole number";
    }
  }

  return fields;
}

export function LlmServerForm({ server, currentDefaultName, onCreated, onDeleted, onDirtyChange }: Props) {
  const [values, setValues] = useState<FormValues>(() => toFormValues(server));
  const [initial, setInitial] = useState<FormValues>(() => toFormValues(server));
  const [errors, setErrors] = useState<FormErrors>({ fields: {} });
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [clearApiKey, setClearApiKey] = useState(false);
  const [testResult, setTestResult] = useState<{ models: string[] } | { error: string } | null>(null);

  const createMutation = useCreateLlmServer();
  const updateMutation = useUpdateLlmServer();
  const deleteMutation = useDeleteLlmServer();
  const setDefaultMutation = useSetDefaultLlmServer();
  const testConnection = useTestConnection();

  const dirty = !shallowEqual(values, initial) || clearApiKey;

  useEffect(() => {
    onDirtyChange(dirty);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dirty]);

  useEffect(() => {
    setValues(toFormValues(server));
    setInitial(toFormValues(server));
    setErrors({ fields: {} });
    setConfirmingDelete(false);
    setClearApiKey(false);
    setTestResult(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [server?.id, server?.updated_at]);

  function updateValue<K extends keyof FormValues>(key: K, value: FormValues[K]) {
    setValues((v) => ({ ...v, [key]: value }));
    setErrors((e) => {
      if (!(key in e.fields)) return e;
      const fields = { ...e.fields };
      delete fields[key as ServerFieldName | OptionFieldName];
      return { ...e, fields };
    });
    setTestResult(null);
  }

  function handleProviderChange(provider: ProviderKind) {
    setValues((v) => ({
      ...v,
      provider,
      ...(server === null ? PROVIDER_META[provider].capabilityDefaults : {}),
    }));
    setTestResult(null);
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const fields = validate(values, server, clearApiKey);
    if (Object.keys(fields).length > 0) {
      setErrors({ fields });
      return;
    }

    if (server) {
      const body = toUpdateBody(values, initial, clearApiKey, server);
      updateMutation.mutate(
        { id: server.id, body },
        { onError: (error) => setErrors(toFormErrors(error)) },
      );
    } else {
      const body = toCreateBody(values);
      createMutation.mutate(body, {
        onSuccess: (created) => onCreated(created),
        onError: (error) => setErrors(toFormErrors(error)),
      });
    }
  }

  function handleDeleteConfirm() {
    if (!server) return;
    deleteMutation.mutate(server.id, {
      onSuccess: () => onDeleted(),
      onError: (error) => setErrors(toFormErrors(error)),
    });
  }

  function handleMakeDefault() {
    if (!server) return;
    setDefaultMutation.mutate(server.id, {
      onError: (error) => setErrors(toFormErrors(error)),
    });
  }

  function handleTestConnection() {
    if (!server) return;
    testConnection.mutate(server.id, {
      onSuccess: (data) => setTestResult({ models: data.models }),
      onError: (error) => setTestResult({ error: toFormErrors(error).form ?? "Connection failed." }),
    });
  }

  const meta = PROVIDER_META[values.provider];
  const isEdit = server !== null;
  const pending = createMutation.isPending || updateMutation.isPending;
  const replacesDefault =
    currentDefaultName != null &&
    currentDefaultName !== server?.name &&
    (isEdit ? !server.is_default : values.is_default);

  return (
    <form className={styles.form} onSubmit={handleSubmit}>
      {errors.form && (
        <Alert tone="error" onDismiss={() => setErrors((e) => ({ ...e, form: undefined }))}>
          {errors.form}
        </Alert>
      )}

      <FormField id="server-name" label="Name" error={errors.fields.name} required>
        {(inputProps) => (
          <input
            {...inputProps}
            className={inputClassName}
            value={values.name}
            onChange={(e) => updateValue("name", e.target.value)}
          />
        )}
      </FormField>

      <FormField id="server-provider" label="Provider">
        {(inputProps) => (
          <select
            {...inputProps}
            className={inputClassName}
            value={values.provider}
            onChange={(e) => handleProviderChange(e.target.value as ProviderKind)}
          >
            {(Object.keys(PROVIDER_META) as ProviderKind[]).map((provider) => (
              <option key={provider} value={provider}>
                {PROVIDER_META[provider].label}
              </option>
            ))}
          </select>
        )}
      </FormField>

      {meta.fields.includes("base_url") && (
        <FormField
          id="server-base-url"
          label="Base URL"
          error={errors.fields.base_url}
          required={meta.required.includes("base_url")}
        >
          {(inputProps) => (
            <input
              {...inputProps}
              className={inputClassName}
              value={values.base_url}
              onChange={(e) => updateValue("base_url", e.target.value)}
            />
          )}
        </FormField>
      )}

      {meta.fields.includes("api_key") && (
        <div className={styles.apiKeyRow}>
          <FormField
            id="server-api-key"
            label="API key"
            error={errors.fields.api_key}
            required={meta.required.includes("api_key") && !(server?.has_api_key && !clearApiKey)}
            hint={server?.has_api_key ? "Leave blank to keep the current key" : undefined}
          >
            {(inputProps) => (
              <input
                {...inputProps}
                type="password"
                className={inputClassName}
                value={values.api_key}
                onChange={(e) => updateValue("api_key", e.target.value)}
                placeholder={server?.has_api_key && !clearApiKey ? "•••••• (set)" : undefined}
              />
            )}
          </FormField>
          {server?.has_api_key &&
            (clearApiKey ? (
              <IconButton
                aria-label="Undo clear"
                onClick={() => {
                  setClearApiKey(false);
                  setTestResult(null);
                }}
              >
                <Undo2 size={16} />
              </IconButton>
            ) : (
              <IconButton
                aria-label="Clear API key"
                onClick={() => {
                  setClearApiKey(true);
                  setTestResult(null);
                }}
              >
                <Trash2 size={16} />
              </IconButton>
            ))}
        </div>
      )}

      {meta.fields.includes("executable_path") && (
        <FormField
          id="server-executable-path"
          label="Executable path"
          error={errors.fields.executable_path}
          hint="Leave blank to use `claude` from PATH"
        >
          {(inputProps) => (
            <input
              {...inputProps}
              className={inputClassName}
              value={values.executable_path}
              onChange={(e) => updateValue("executable_path", e.target.value)}
            />
          )}
        </FormField>
      )}

      {meta.optionFields.includes("system_prompt") && (
        <FormField id="server-system-prompt" label="System prompt" error={errors.fields.system_prompt}>
          {(inputProps) => (
            <textarea
              {...inputProps}
              className={inputClassName}
              rows={3}
              value={values.system_prompt}
              onChange={(e) => updateValue("system_prompt", e.target.value)}
            />
          )}
        </FormField>
      )}

      {meta.optionFields.includes("max_tokens") && (
        <FormField
          id="server-max-tokens"
          label="Max tokens"
          error={errors.fields.max_tokens}
          hint="Leave blank for 16000"
        >
          {(inputProps) => (
            <input
              {...inputProps}
              type="number"
              className={inputClassName}
              value={values.max_tokens}
              onChange={(e) => updateValue("max_tokens", e.target.value)}
            />
          )}
        </FormField>
      )}

      <div className={styles.modelRow}>
        <FormField id="server-default-model" label="Default model" error={errors.fields.default_model}>
          {(inputProps) => (
            <>
              <input
                {...inputProps}
                className={inputClassName}
                list="server-default-model-options"
                value={values.default_model}
                onChange={(e) => updateValue("default_model", e.target.value)}
              />
              <datalist id="server-default-model-options">
                {testResult && "models" in testResult && testResult.models.map((model) => (
                  <option key={model} value={model} />
                ))}
              </datalist>
            </>
          )}
        </FormField>
        <button
          type="button"
          className={styles.testConnectionButton}
          onClick={handleTestConnection}
          disabled={server === null || dirty}
          title={server === null || dirty ? "Save the server first" : undefined}
        >
          <PlugZap size={16} aria-hidden="true" />
          Test connection
        </button>
      </div>

      {testConnection.isPending && <HexLoader size="1.2em" />}
      {testResult && "models" in testResult && !testConnection.isPending && (
        <Alert tone="success">Connected. {testResult.models.length} models available.</Alert>
      )}
      {testResult && "error" in testResult && !testConnection.isPending && (
        <Alert tone="error">{testResult.error}</Alert>
      )}

      <fieldset className={styles.fieldset}>
        <legend>Capabilities</legend>
        {CAPABILITY_FIELDS.map(({ key, label }) => (
          <label key={key} className={styles.checkboxRow}>
            <input
              type="checkbox"
              checked={values[key]}
              onChange={(e) => updateValue(key, e.target.checked)}
            />
            {label}
          </label>
        ))}
      </fieldset>

      <div>
        <label className={styles.checkboxRow}>
          <input
            type="checkbox"
            checked={values.is_enabled}
            onChange={(e) => updateValue("is_enabled", e.target.checked)}
          />
          Enabled
        </label>
        {isEdit && server.is_default && (
          <p className={styles.hint}>The default server cannot be disabled.</p>
        )}
      </div>

      <div className={styles.defaultRow}>
        {!isEdit && (
          <label className={styles.checkboxRow}>
            <input
              type="checkbox"
              checked={values.is_default}
              onChange={(e) => updateValue("is_default", e.target.checked)}
            />
            Make this the default server
          </label>
        )}
        {isEdit && !server.is_default && (
          <button
            type="button"
            onClick={handleMakeDefault}
            disabled={setDefaultMutation.isPending}
          >
            Make default
          </button>
        )}
        {isEdit && server.is_default && <span className={styles.badge}>Default server</span>}
      </div>
      {replacesDefault && (
        <p className={styles.hint}>Replaces the current default: {currentDefaultName}</p>
      )}

      <div className={styles.actions}>
        <button type="submit" disabled={pending || (isEdit && !dirty)}>
          {pending ? <HexLoader size="1em" /> : isEdit ? "Save" : "Create"}
        </button>

        {isEdit &&
          (confirmingDelete ? (
            <div className={styles.confirmDelete}>
              <span>Delete &apos;{server.name}&apos;?</span>
              <button type="button" onClick={handleDeleteConfirm} disabled={deleteMutation.isPending}>
                Confirm delete
              </button>
              <button type="button" onClick={() => setConfirmingDelete(false)}>
                Cancel
              </button>
            </div>
          ) : (
            <button
              type="button"
              className={styles.danger}
              onClick={() => setConfirmingDelete(true)}
              disabled={server.is_default}
              title={
                server.is_default
                  ? "The default server cannot be deleted; set another default first"
                  : undefined
              }
            >
              Delete
            </button>
          ))}
      </div>
    </form>
  );
}
