import { act } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { FakeWebSocket } from "@/test/fakeWebSocket";
import { renderWithQuery } from "@/test/render";
import { server } from "@/test/server";

import { ChatPanel } from "./ChatPanel";

// Setting an activeRun opens a real WebSocket in jsdom (see the note near the
// top of SettingsModal.test.tsx), so stub it with FakeWebSocket, which never
// connects on its own -- tests drive it explicitly via open()/emit()/close().
describe("ChatPanel", () => {
  beforeEach(() => {
    FakeWebSocket.reset();
    vi.stubGlobal("WebSocket", FakeWebSocket);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows the user's message immediately after submitting", async () => {
    const { findByRole, findByLabelText, user } = renderWithQuery(<ChatPanel />);

    const textarea = await findByRole("textbox", { name: "Prompt" });
    await user.type(textarea, "Hello there");
    await user.click(await findByRole("button", { name: "Send" }));

    const userBubble = await findByLabelText("You");
    expect(userBubble).toHaveTextContent("Hello there");
    await vi.waitFor(() => expect(textarea).toHaveValue(""));
  });

  it("renders streamed tokens in the live assistant bubble", async () => {
    const { findByRole, findByLabelText, user } = renderWithQuery(<ChatPanel />);

    const textarea = await findByRole("textbox", { name: "Prompt" });
    await user.type(textarea, "Hello there");
    await user.click(await findByRole("button", { name: "Send" }));

    await vi.waitFor(() => expect(FakeWebSocket.latestSocket()).toBeDefined());
    const socket = FakeWebSocket.latestSocket()!;
    act(() => {
      socket.open();
      socket.emit({ type: "status", run_id: "run-1", at: "now", data: { status: "running" } });
      socket.emit({ type: "token", run_id: "run-1", at: "now", data: { text: "Hi " } });
      socket.emit({ type: "token", run_id: "run-1", at: "now", data: { text: "there!" } });
    });

    const assistantBubble = await findByLabelText("Assistant");
    await vi.waitFor(() => expect(assistantBubble).toHaveTextContent("Hi there!"));
  });

  it("disables Send while live and Enter does not submit another run", async () => {
    const { findByRole, user } = renderWithQuery(<ChatPanel />);

    const textarea = await findByRole("textbox", { name: "Prompt" });
    await user.type(textarea, "First message");
    await user.click(await findByRole("button", { name: "Send" }));

    await vi.waitFor(() => expect(FakeWebSocket.latestSocket()).toBeDefined());
    act(() => {
      FakeWebSocket.latestSocket()!.open();
      FakeWebSocket.latestSocket()!.emit({
        type: "status",
        run_id: "run-1",
        at: "now",
        data: { status: "running" },
      });
    });

    const sendButton = await findByRole("button", { name: "Send" });
    await vi.waitFor(() => expect(sendButton).toBeDisabled());

    await user.type(textarea, "Second message");
    await user.keyboard("{Enter}");

    // Only the first run's POST should have happened.
    expect(FakeWebSocket.instances).toHaveLength(1);
  });

  it("swaps the live bubble for canonical turns and closes the socket on a terminal status", async () => {
    server.use(
      http.get("/api/v1/conversations/:id", ({ params }) => {
        return HttpResponse.json({
          id: params.id,
          turns: [
            { role: "user", content: "Hello there", at: "now", partial: false, usage: null },
            { role: "assistant", content: "Hi there!", at: "now", partial: false, usage: null },
          ],
          active_run_id: null,
        });
      }),
    );

    const { findByRole, findByLabelText, user } = renderWithQuery(<ChatPanel />);

    const textarea = await findByRole("textbox", { name: "Prompt" });
    await user.type(textarea, "Hello there");
    await user.click(await findByRole("button", { name: "Send" }));

    await vi.waitFor(() => expect(FakeWebSocket.latestSocket()).toBeDefined());
    const socket = FakeWebSocket.latestSocket()!;
    act(() => {
      socket.open();
      socket.emit({ type: "token", run_id: "run-1", at: "now", data: { text: "Hi there!" } });
      socket.emit({ type: "status", run_id: "run-1", at: "now", data: { status: "succeeded" } });
    });

    await vi.waitFor(async () => {
      const assistantBubbles = await findByLabelText("Assistant");
      expect(assistantBubbles).toHaveTextContent("Hi there!");
    });
    const sendButton = await findByRole("button", { name: "Send" });
    await vi.waitFor(() => expect(sendButton).not.toBeDisabled());
    await vi.waitFor(() => expect(socket.closed).toBe(true));
  });

  it("shows 'Interrupted' for a partial turn", async () => {
    server.use(
      http.get("/api/v1/conversations/:id", ({ params }) => {
        return HttpResponse.json({
          id: params.id,
          turns: [
            { role: "user", content: "Hello", at: "now", partial: false, usage: null },
            { role: "assistant", content: "Cut off", at: "now", partial: true, usage: null },
          ],
          active_run_id: null,
        });
      }),
    );

    const { findByRole, user } = renderWithQuery(<ChatPanel />);

    const textarea = await findByRole("textbox", { name: "Prompt" });
    await user.type(textarea, "Hello");
    await user.click(await findByRole("button", { name: "Send" }));

    await vi.waitFor(() => expect(FakeWebSocket.latestSocket()).toBeDefined());
    act(() => {
      FakeWebSocket.latestSocket()!.open();
      FakeWebSocket.latestSocket()!.emit({
        type: "status",
        run_id: "run-1",
        at: "now",
        data: { status: "failed" },
      });
    });

    await vi.waitFor(async () => {
      expect(await findByRole("button", { name: "Send" })).not.toBeDisabled();
    });
    expect(await findByRole("article", { name: "Assistant" })).toHaveTextContent("Interrupted");
  });

  it("shows an alert with the error message when a run fails", async () => {
    const { findByRole, user } = renderWithQuery(<ChatPanel />);

    const textarea = await findByRole("textbox", { name: "Prompt" });
    await user.type(textarea, "Hello");
    await user.click(await findByRole("button", { name: "Send" }));

    await vi.waitFor(() => expect(FakeWebSocket.latestSocket()).toBeDefined());
    act(() => {
      FakeWebSocket.latestSocket()!.open();
      FakeWebSocket.latestSocket()!.emit({
        type: "error",
        run_id: "run-1",
        at: "now",
        data: { message: "The model timed out" },
      });
      FakeWebSocket.latestSocket()!.emit({
        type: "status",
        run_id: "run-1",
        at: "now",
        data: { status: "failed" },
      });
    });

    const alert = await findByRole("alert");
    expect(alert).toHaveTextContent("The model timed out");
  });
});
