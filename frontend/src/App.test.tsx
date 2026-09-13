import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "@/App";
import { FakeWebSocket } from "@/test/fakeWebSocket";
import { renderWithQuery } from "@/test/render";

describe("App", () => {
  // Submitting a message opens a real WebSocket in jsdom (see the note near
  // the top of SettingsModal.test.tsx), so stub it with FakeWebSocket.
  beforeEach(() => {
    FakeWebSocket.reset();
    vi.stubGlobal("WebSocket", FakeWebSocket);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("resets the transcript and textarea when 'New chat' is clicked", async () => {
    const { findByRole, findByLabelText, user } = renderWithQuery(<App />);

    const textarea = await findByRole("textbox", { name: "Prompt" });
    await user.type(textarea, "Hello there");
    await user.click(await findByRole("button", { name: "Send" }));

    await findByLabelText("You");
    expect(textarea).not.toHaveValue("Hello there");

    await user.click(await findByRole("button", { name: "New chat" }));

    const freshTextarea = await findByRole("textbox", { name: "Prompt" });
    expect(freshTextarea).toHaveValue("");
    expect(document.querySelectorAll('[aria-label="You"]')).toHaveLength(0);
  });
});
