import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";

import { makeServer, SEED_CLAUDE_NAME, SEED_LOCAL_NAME, servers } from "@/test/fixtures/llmServers";
import { renderWithQuery } from "@/test/render";
import { server } from "@/test/server";

import { LlmServersSection } from "./LlmServersSection";

const LOCAL_OPTION = `${SEED_LOCAL_NAME} (default)`;

describe("LlmServersSection", () => {
  it("lists both servers, preselects the default, and shows its name", async () => {
    const { findByRole } = renderWithQuery(<LlmServersSection />);

    const select = await findByRole("combobox", { name: "Server" });
    expect(select).toHaveDisplayValue(LOCAL_OPTION);

    const nameInput = await findByRole("textbox", { name: "Name" });
    expect(nameInput).toHaveValue(SEED_LOCAL_NAME);
  });

  it("swaps provider-specific fields when selecting a different server", async () => {
    const { findByRole, queryByRole, findByPlaceholderText, user } = renderWithQuery(
      <LlmServersSection />,
    );

    const select = await findByRole("combobox", { name: "Server" });
    await user.selectOptions(select, SEED_CLAUDE_NAME);

    expect(queryByRole("textbox", { name: "Base URL" })).not.toBeInTheDocument();
    const apiKeyInput = await findByPlaceholderText("•••••• (set)");
    expect(apiKeyInput).toBeInTheDocument();
  });

  it("clears the form and shows the default checkbox when New is clicked", async () => {
    const { findByRole, user } = renderWithQuery(<LlmServersSection />);

    const newButton = await findByRole("button", { name: "New" });
    await user.click(newButton);

    const nameInput = await findByRole("textbox", { name: "Name" });
    expect(nameInput).toHaveValue("");
    expect(await findByRole("checkbox", { name: "Make this the default server" })).toBeInTheDocument();
  });

  it("adds and selects a new server on create success", async () => {
    const { findByRole, user } = renderWithQuery(<LlmServersSection />);

    await user.click(await findByRole("button", { name: "New" }));
    await user.type(await findByRole("textbox", { name: "Name" }), "Fresh Server");
    await user.type(await findByRole("textbox", { name: "Base URL" }), "http://example.com/v1");
    await user.click(await findByRole("button", { name: "Create" }));

    const select = await findByRole("combobox", { name: "Server" });
    expect(await findByRole("option", { name: "Fresh Server" })).toBeInTheDocument();
    expect(select).toHaveDisplayValue("Fresh Server");
  });

  it("shows a duplicate-name 409 message in the form alert", async () => {
    const { findByRole, user } = renderWithQuery(<LlmServersSection />);

    await user.click(await findByRole("button", { name: "New" }));
    await user.type(await findByRole("textbox", { name: "Name" }), SEED_CLAUDE_NAME);
    await user.type(await findByRole("textbox", { name: "Base URL" }), "http://example.com/v1");
    await user.click(await findByRole("button", { name: "Create" }));

    const alert = await findByRole("alert");
    expect(alert).toHaveTextContent(`An LLM server named '${SEED_CLAUDE_NAME}' already exists`);
  });

  it("blocks submit client-side when openai_compatible is missing a base URL, without a request", async () => {
    const createSpy = vi.fn();
    server.use(
      http.post("/api/v1/llm-servers", () => {
        createSpy();
        return HttpResponse.json({ detail: "should not be called" }, { status: 500 });
      }),
    );

    const { findByRole, user } = renderWithQuery(<LlmServersSection />);

    await user.click(await findByRole("button", { name: "New" }));
    await user.type(await findByRole("textbox", { name: "Name" }), "No Base URL");
    await user.click(await findByRole("button", { name: "Create" }));

    expect(await findByRole("alert")).toHaveTextContent("Base URL is required.");
    expect(createSpy).not.toHaveBeenCalled();
  });

  it("surfaces a 422 body-level error under Base URL", async () => {
    server.use(
      http.post("/api/v1/llm-servers", () =>
        HttpResponse.json(
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
        ),
      ),
    );

    const { findByRole, user } = renderWithQuery(<LlmServersSection />);

    await user.click(await findByRole("button", { name: "New" }));
    await user.type(await findByRole("textbox", { name: "Name" }), "Errored Server");
    await user.type(await findByRole("textbox", { name: "Base URL" }), "http://example.com/v1");
    await user.click(await findByRole("button", { name: "Create" }));

    expect(await findByRole("alert")).toHaveTextContent(
      "base_url is required for openai_compatible servers",
    );
  });

  // Captures outgoing PATCH bodies via msw's life-cycle events rather than
  // overriding the handler, so the fixture's own mutation + updated_at bump
  // still happens and the list refetch reflects it (which LlmServerForm's
  // remount-on-updated_at relies on).
  function capturePatchBodies(): Record<string, unknown>[] {
    const bodies: Record<string, unknown>[] = [];
    const listener = async ({ request }: { request: Request }) => {
      if (request.method === "PATCH") {
        bodies.push((await request.clone().json()) as Record<string, unknown>);
      }
    };
    server.events.on("request:start", listener);
    return bodies;
  }

  it("saves only the changed keys when editing the name, and disables Save afterward", async () => {
    const patchBodies = capturePatchBodies();
    const { findByRole, user } = renderWithQuery(<LlmServersSection />);

    const nameInput = await findByRole("textbox", { name: "Name" });
    await user.clear(nameInput);
    await user.type(nameInput, "Renamed Local");

    const saveButton = await findByRole("button", { name: "Save" });
    await user.click(saveButton);

    await vi.waitFor(() => expect(patchBodies).toEqual([{ name: "Renamed Local" }]));
    await vi.waitFor(async () => {
      expect(await findByRole("button", { name: "Save" })).toBeDisabled();
    });
  });

  it("omits api_key when left blank, and sends null after Clear API key", async () => {
    // api_key is optional (not required) for openai_compatible, so a server
    // with has_api_key: true here exercises "leave blank / clear" without
    // tripping the provider's required-field validation (unlike Claude,
    // where anthropic requires an api_key).
    const optionalKeyServer = makeServer({
      name: "Optional Key Server",
      provider: "openai_compatible",
      base_url: "http://example.com/v1",
      has_api_key: true,
    });
    servers.push(optionalKeyServer);

    const patchBodies = capturePatchBodies();
    const { findByRole, user } = renderWithQuery(<LlmServersSection />);

    const select = await findByRole("combobox", { name: "Server" });
    await user.selectOptions(select, optionalKeyServer.name);

    const modelInput = await findByRole("combobox", { name: "Default model" });
    await user.type(modelInput, "-2");
    await user.click(await findByRole("button", { name: "Save" }));

    await vi.waitFor(() => expect(patchBodies).toHaveLength(1));
    expect(patchBodies[0]).not.toHaveProperty("api_key");
    // Wait for the post-save remount (keyed on the refetched updated_at) to
    // settle before interacting again.
    await vi.waitFor(async () => {
      expect(await findByRole("button", { name: "Save" })).toBeDisabled();
    });

    await user.click(await findByRole("button", { name: "Clear API key" }));
    await user.click(await findByRole("button", { name: "Save" }));

    await vi.waitFor(() => expect(patchBodies).toHaveLength(2));
    expect(patchBodies[1]?.api_key).toBeNull();
  });

  it("disables Delete on the default server with an explanatory title", async () => {
    const { findByRole } = renderWithQuery(<LlmServersSection />);

    const deleteButton = await findByRole("button", { name: "Delete" });
    expect(deleteButton).toBeDisabled();
    expect(deleteButton).toHaveAttribute(
      "title",
      "The default server cannot be deleted; set another default first",
    );
  });

  it("deletes a non-default server through the confirm step and falls back to the default", async () => {
    const { findByRole, queryByRole, user } = renderWithQuery(<LlmServersSection />);

    const select = await findByRole("combobox", { name: "Server" });
    await user.selectOptions(select, SEED_CLAUDE_NAME);

    await user.click(await findByRole("button", { name: "Delete" }));
    await user.click(await findByRole("button", { name: "Confirm delete" }));

    await vi.waitFor(() => {
      expect(queryByRole("option", { name: SEED_CLAUDE_NAME })).not.toBeInTheDocument();
    });
    expect(await findByRole("combobox", { name: "Server" })).toHaveDisplayValue(LOCAL_OPTION);
  });

  it("shows models in the datalist and a success message on Test connection", async () => {
    const { findByRole, container, user } = renderWithQuery(<LlmServersSection />);

    await user.click(await findByRole("button", { name: "Test connection" }));

    expect(await findByRole("status")).toHaveTextContent("Connected. 2 models available.");
    expect(container.querySelector('option[value="m-a"]')).toBeInTheDocument();
  });

  it("clears a successful Test connection result when the Name field is edited", async () => {
    const { findByRole, queryByRole, user } = renderWithQuery(<LlmServersSection />);

    await user.click(await findByRole("button", { name: "Test connection" }));
    expect(await findByRole("status")).toHaveTextContent("Connected. 2 models available.");

    const nameInput = await findByRole("textbox", { name: "Name" });
    await user.type(nameInput, "x");

    expect(queryByRole("status")).not.toBeInTheDocument();
  });

  it("shows a 502 upstream error on Test connection", async () => {
    server.use(
      http.get("/api/v1/llm-servers/:id/models", () =>
        HttpResponse.json({ detail: `${SEED_LOCAL_NAME}: boom` }, { status: 502 }),
      ),
    );

    const { findByRole, user } = renderWithQuery(<LlmServersSection />);

    await user.click(await findByRole("button", { name: "Test connection" }));

    expect(await findByRole("alert")).toHaveTextContent(`${SEED_LOCAL_NAME}: boom`);
  });

  it("disables Test connection while the form is dirty", async () => {
    const { findByRole, user } = renderWithQuery(<LlmServersSection />);

    const modelInput = await findByRole("combobox", { name: "Default model" });
    await user.type(modelInput, "some-model");

    const testButton = await findByRole("button", { name: "Test connection" });
    expect(testButton).toBeDisabled();
    expect(testButton).toHaveAttribute("title", "Save the server first");
  });

  it("moves the default marker when Make default is used on another server", async () => {
    const { findByRole, user } = renderWithQuery(<LlmServersSection />);

    const select = await findByRole("combobox", { name: "Server" });
    await user.selectOptions(select, SEED_CLAUDE_NAME);

    await user.click(await findByRole("button", { name: "Make default" }));

    await vi.waitFor(async () => {
      expect(await findByRole("option", { name: `${SEED_CLAUDE_NAME} (default)` })).toBeInTheDocument();
    });
    expect(
      (await findByRole("option", { name: SEED_LOCAL_NAME })) as HTMLOptionElement,
    ).toBeInTheDocument();
  });

  it("shows a 409 message when disabling the default server", async () => {
    const { findByRole, user } = renderWithQuery(<LlmServersSection />);

    const enabledCheckbox = await findByRole("checkbox", { name: "Enabled" });
    await user.click(enabledCheckbox);
    await user.click(await findByRole("button", { name: "Save" }));

    expect(await findByRole("alert")).toHaveTextContent(
      "The default server cannot be disabled; set another default first",
    );
  });

  it("asks for confirmation before switching servers with unsaved changes, and keeps the selection when declined", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);
    const { findByRole, user } = renderWithQuery(<LlmServersSection />);

    const nameInput = await findByRole("textbox", { name: "Name" });
    await user.clear(nameInput);
    await user.type(nameInput, "Dirty Name");

    const select = await findByRole("combobox", { name: "Server" });
    await user.selectOptions(select, SEED_CLAUDE_NAME);

    expect(confirmSpy).toHaveBeenCalledWith("Discard unsaved changes?");
    expect(select).toHaveDisplayValue(LOCAL_OPTION);
    expect(await findByRole("textbox", { name: "Name" })).toHaveValue("Dirty Name");

    confirmSpy.mockRestore();
  });
});
