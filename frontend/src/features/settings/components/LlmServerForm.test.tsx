import { describe, expect, it, vi } from "vitest";

import { makeServer, SEED_CLAUDE_NAME, servers } from "@/test/fixtures/llmServers";
import { renderWithQuery } from "@/test/render";
import { server } from "@/test/server";

import { LlmServersSection } from "./LlmServersSection";

describe("LlmServerForm options", () => {
  it("shows Max tokens only for the anthropic provider", async () => {
    const { findByRole, queryByRole, user } = renderWithQuery(<LlmServersSection />);

    // Local (from env) is openai_compatible: no Max tokens field.
    expect(queryByRole("spinbutton", { name: "Max tokens" })).not.toBeInTheDocument();
    expect(await findByRole("textbox", { name: "System prompt" })).toBeInTheDocument();

    const select = await findByRole("combobox", { name: "Server" });
    await user.selectOptions(select, SEED_CLAUDE_NAME);

    expect(await findByRole("spinbutton", { name: "Max tokens" })).toBeInTheDocument();
  });

  function capturePatchBodies(): Record<string, unknown>[] {
    const bodies: Record<string, unknown>[] = [];
    server.events.on("request:start", async ({ request }) => {
      if (request.method === "PATCH") {
        bodies.push((await request.clone().json()) as Record<string, unknown>);
      }
    });
    return bodies;
  }

  it("sends options.system_prompt when saving a system prompt", async () => {
    const patchBodies = capturePatchBodies();
    const { findByRole, user } = renderWithQuery(<LlmServersSection />);

    const systemPrompt = await findByRole("textbox", { name: "System prompt" });
    await user.type(systemPrompt, "Be concise");
    await user.click(await findByRole("button", { name: "Save" }));

    await vi.waitFor(() => expect(patchBodies).toHaveLength(1));
    expect(patchBodies[0]?.options).toEqual({ system_prompt: "Be concise" });
  });

  it("omits max_tokens from options when left blank", async () => {
    const patchBodies = capturePatchBodies();
    const { findByRole, user } = renderWithQuery(<LlmServersSection />);

    const select = await findByRole("combobox", { name: "Server" });
    await user.selectOptions(select, SEED_CLAUDE_NAME);

    const systemPrompt = await findByRole("textbox", { name: "System prompt" });
    await user.type(systemPrompt, "Be concise");
    await user.click(await findByRole("button", { name: "Save" }));

    await vi.waitFor(() => expect(patchBodies).toHaveLength(1));
    expect(patchBodies[0]?.options).toEqual({ system_prompt: "Be concise" });
    expect(patchBodies[0]?.options).not.toHaveProperty("max_tokens");
  });

  it("keeps API-only option keys already stored on the server when saving", async () => {
    const serverWithExtraOptions = makeServer({
      name: "Server With Request Options",
      provider: "openai_compatible",
      base_url: "http://example.com/v1",
      options: { request: { temperature: 0.2 } },
    });
    servers.push(serverWithExtraOptions);

    const patchBodies = capturePatchBodies();
    const { findByRole, user } = renderWithQuery(<LlmServersSection />);

    const select = await findByRole("combobox", { name: "Server" });
    await user.selectOptions(select, serverWithExtraOptions.name);

    const systemPrompt = await findByRole("textbox", { name: "System prompt" });
    await user.type(systemPrompt, "Be concise");
    await user.click(await findByRole("button", { name: "Save" }));

    await vi.waitFor(() => expect(patchBodies).toHaveLength(1));
    expect(patchBodies[0]?.options).toEqual({
      request: { temperature: 0.2 },
      system_prompt: "Be concise",
    });
  });

  it("shows a field error for an invalid max tokens value", async () => {
    const { findByRole, user } = renderWithQuery(<LlmServersSection />);

    const select = await findByRole("combobox", { name: "Server" });
    await user.selectOptions(select, SEED_CLAUDE_NAME);

    const maxTokens = await findByRole("spinbutton", { name: "Max tokens" });
    await user.type(maxTokens, "-5");
    await user.click(await findByRole("button", { name: "Save" }));

    expect(await findByRole("alert")).toHaveTextContent("Must be a positive whole number");
  });
});
