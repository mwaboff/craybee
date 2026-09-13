import { within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import App from "@/App";
import { renderWithQuery } from "@/test/render";

// ChatPanel only opens its WebSocket once a run starts (useRunStream(null) is
// a no-op), so <App/> can be rendered directly here without stubbing
// globalThis.WebSocket.
describe("SettingsModal", () => {
  it("opens from the gear button, shows the LLM Servers section, and Escape closes it back to the gear", async () => {
    const { getByRole, findByRole, user } = renderWithQuery(<App />);

    const trigger = getByRole("button", { name: "Settings" });
    await user.click(trigger);

    const dialog = await findByRole("dialog", { name: "Settings" });
    expect(dialog).toBeInTheDocument();

    const nav = within(dialog).getByRole("navigation", { name: "Settings sections" });
    const sectionButton = within(nav).getByRole("button", { name: "LLM Servers" });
    expect(sectionButton).toHaveAttribute("aria-current", "page");

    await user.keyboard("{Escape}");
    expect(dialog).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("closes via the Close button and restores focus to the gear button", async () => {
    const { getByRole, findByRole, user } = renderWithQuery(<App />);

    const trigger = getByRole("button", { name: "Settings" });
    await user.click(trigger);

    const dialog = await findByRole("dialog", { name: "Settings" });
    const closeButton = within(dialog).getByRole("button", { name: "Close" });
    await user.click(closeButton);

    expect(dialog).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });
});
