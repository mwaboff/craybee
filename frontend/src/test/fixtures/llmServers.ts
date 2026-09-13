import { http, HttpResponse } from "msw";

import type {
  LLMServer,
  LLMServerCreate,
  LLMServerUpdate,
  ProviderKind,
} from "@/features/settings/types";
import { PROVIDER_META } from "@/features/settings/types";

export const SEED_LOCAL_NAME = "Local (from env)";
export const SEED_CLAUDE_NAME = "Claude";

const FIXED_NOW = "2026-01-01T00:00:00.000Z";

function seedServers(): LLMServer[] {
  return [
    {
      id: "srv-local",
      name: SEED_LOCAL_NAME,
      provider: "openai_compatible",
      base_url: "http://localhost:11434/v1",
      has_api_key: false,
      executable_path: null,
      default_model: null,
      options: {},
      supports_tools: false,
      supports_vision: false,
      supports_streaming: true,
      supports_structured_output: false,
      is_default: true,
      is_enabled: true,
      created_at: FIXED_NOW,
      updated_at: FIXED_NOW,
    },
    {
      id: "srv-claude",
      name: SEED_CLAUDE_NAME,
      provider: "anthropic",
      base_url: null,
      has_api_key: true,
      executable_path: null,
      default_model: "claude-sonnet-5",
      options: {},
      supports_tools: true,
      supports_vision: true,
      supports_streaming: true,
      supports_structured_output: true,
      is_default: false,
      is_enabled: true,
      created_at: FIXED_NOW,
      updated_at: FIXED_NOW,
    },
  ];
}

export let servers: LLMServer[] = seedServers();

export function resetFixtures(): void {
  servers = seedServers();
}

let idCounter = 0;

export function makeServer(overrides: Partial<LLMServer> = {}): LLMServer {
  idCounter += 1;
  const provider: ProviderKind = overrides.provider ?? "openai_compatible";
  const defaults = PROVIDER_META[provider].capabilityDefaults;
  return {
    id: `srv-fixture-${idCounter}`,
    name: `Fixture Server ${idCounter}`,
    provider,
    base_url: null,
    has_api_key: false,
    executable_path: null,
    default_model: null,
    options: {},
    ...defaults,
    is_default: false,
    is_enabled: true,
    created_at: FIXED_NOW,
    updated_at: FIXED_NOW,
    ...overrides,
  };
}

export const llmServerHandlers = [
  http.get("/api/v1/llm-servers", () => {
    return HttpResponse.json(servers);
  }),

  http.post("/api/v1/llm-servers", async ({ request }) => {
    const body = (await request.json()) as LLMServerCreate;

    if (!body.name || body.name.length < 1) {
      return HttpResponse.json(
        {
          detail: [
            {
              loc: ["body", "name"],
              msg: "String should have at least 1 character",
              type: "string_too_short",
            },
          ],
        },
        { status: 422 },
      );
    }

    if (body.provider === "openai_compatible" && !body.base_url) {
      return HttpResponse.json(
        {
          detail: [
            {
              loc: ["body"],
              msg: "Value error, base_url is required for openai_compatible servers",
              type: "value_error",
            },
          ],
        },
        { status: 422 },
      );
    }

    if (body.provider === "anthropic" && !body.api_key) {
      return HttpResponse.json(
        {
          detail: [
            {
              loc: ["body"],
              msg: "Value error, api_key is required for anthropic servers",
              type: "value_error",
            },
          ],
        },
        { status: 422 },
      );
    }

    if (servers.some((s) => s.name === body.name)) {
      return HttpResponse.json(
        { detail: `An LLM server named '${body.name}' already exists` },
        { status: 409 },
      );
    }

    const defaults = PROVIDER_META[body.provider].capabilityDefaults;
    const now = new Date().toISOString();

    if (body.is_default) {
      servers = servers.map((s) => ({ ...s, is_default: false }));
    }

    const created: LLMServer = {
      id: `srv-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      name: body.name,
      provider: body.provider,
      base_url: body.base_url ?? null,
      has_api_key: Boolean(body.api_key),
      executable_path: body.executable_path ?? null,
      default_model: body.default_model ?? null,
      options: body.options ?? {},
      supports_tools: body.supports_tools ?? defaults.supports_tools,
      supports_vision: body.supports_vision ?? defaults.supports_vision,
      supports_streaming: body.supports_streaming ?? defaults.supports_streaming,
      supports_structured_output:
        body.supports_structured_output ?? defaults.supports_structured_output,
      is_default: body.is_default ?? false,
      is_enabled: body.is_enabled ?? true,
      created_at: now,
      updated_at: now,
    };
    servers.push(created);
    return HttpResponse.json(created, { status: 201 });
  }),

  http.patch("/api/v1/llm-servers/:id", async ({ request, params }) => {
    const server = servers.find((s) => s.id === params.id);
    if (!server) {
      return HttpResponse.json({ detail: "Not found" }, { status: 404 });
    }
    const body = (await request.json()) as LLMServerUpdate & { api_key?: string | null };

    const next: LLMServer = { ...server };
    for (const [key, value] of Object.entries(body)) {
      if (key === "api_key") {
        next.has_api_key = value !== null && value !== undefined;
        continue;
      }
      (next as unknown as Record<string, unknown>)[key] = value;
    }

    const provider = next.provider;
    if (provider === "openai_compatible" && !next.base_url) {
      return HttpResponse.json(
        { detail: "base_url is required for openai_compatible servers" },
        { status: 400 },
      );
    }
    if (provider === "anthropic" && !next.has_api_key) {
      return HttpResponse.json(
        { detail: "api_key is required for anthropic servers" },
        { status: 400 },
      );
    }

    if (next.is_default && !next.is_enabled) {
      return HttpResponse.json(
        { detail: "The default server cannot be disabled; set another default first" },
        { status: 409 },
      );
    }

    next.updated_at = new Date().toISOString();
    servers = servers.map((s) => (s.id === next.id ? next : s));
    return HttpResponse.json(next);
  }),

  http.delete("/api/v1/llm-servers/:id", ({ params }) => {
    const server = servers.find((s) => s.id === params.id);
    if (!server) {
      return HttpResponse.json({ detail: "Not found" }, { status: 404 });
    }
    if (server.is_default) {
      return HttpResponse.json(
        { detail: "Cannot delete the default server; set another default first" },
        { status: 409 },
      );
    }
    servers = servers.filter((s) => s.id !== server.id);
    return new HttpResponse(null, { status: 204 });
  }),

  http.post("/api/v1/llm-servers/:id/default", ({ params }) => {
    const server = servers.find((s) => s.id === params.id);
    if (!server) {
      return HttpResponse.json({ detail: "Not found" }, { status: 404 });
    }
    if (!server.is_enabled) {
      return HttpResponse.json(
        { detail: "A disabled server cannot be the default" },
        { status: 409 },
      );
    }
    servers = servers.map((s) => ({ ...s, is_default: s.id === server.id }));
    const updated = servers.find((s) => s.id === server.id);
    return HttpResponse.json(updated);
  }),

  http.get("/api/v1/llm-servers/:id/models", ({ params }) => {
    const server = servers.find((s) => s.id === params.id);
    if (!server) {
      return HttpResponse.json({ detail: "Not found" }, { status: 404 });
    }
    return HttpResponse.json({ models: ["m-a", "m-b"] });
  }),
];
