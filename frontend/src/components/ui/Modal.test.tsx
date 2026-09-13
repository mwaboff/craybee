import { cleanup, fireEvent, render, screen, waitForElementToBeRemoved } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, describe, expect, it } from "vitest";

import { Modal } from "./Modal";

function Harness({ initialOpen = true }: { initialOpen?: boolean }) {
  const [open, setOpen] = useState(initialOpen);
  return (
    <>
      <button data-testid="opener" onClick={() => setOpen(true)}>
        Open
      </button>
      <Modal open={open} onClose={() => setOpen(false)} labelledBy="modal-title">
        <h2 id="modal-title">Title</h2>
        <p>Body</p>
      </Modal>
    </>
  );
}

afterEach(() => {
  cleanup();
});

describe("Modal", () => {
  it("renders nothing when open is false", () => {
    render(
      <Modal open={false} onClose={() => {}} labelledBy="title">
        <p>content</p>
      </Modal>,
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("renders dialog semantics when open", () => {
    render(
      <Modal open onClose={() => {}} labelledBy="title">
        <h2 id="title">Title</h2>
      </Modal>,
    );
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog).toHaveAttribute("aria-labelledby", "title");
  });

  it("calls onClose on Escape", async () => {
    let closed = false;
    render(
      <Modal open onClose={() => (closed = true)} labelledBy="title">
        <h2 id="title">Title</h2>
      </Modal>,
    );
    fireEvent.keyDown(document, { key: "Escape" });
    expect(closed).toBe(true);
  });

  it("calls onClose on overlay mousedown but not on panel mousedown", () => {
    let closeCount = 0;
    render(
      <Modal open onClose={() => (closeCount += 1)} labelledBy="title">
        <h2 id="title">Title</h2>
      </Modal>,
    );
    const dialog = screen.getByRole("dialog");
    fireEvent.mouseDown(dialog);
    expect(closeCount).toBe(0);

    const overlay = dialog.parentElement as HTMLElement;
    fireEvent.mouseDown(overlay);
    expect(closeCount).toBe(1);
  });

  it("returns focus to the previously focused element after closing", async () => {
    const user = userEvent.setup();
    render(<Harness initialOpen={false} />);

    const opener = screen.getByTestId("opener");
    opener.focus();
    expect(document.activeElement).toBe(opener);

    await user.click(opener);
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toBeInTheDocument();

    fireEvent.keyDown(document, { key: "Escape" });
    await waitForElementToBeRemoved(() => screen.queryByRole("dialog"));

    expect(document.activeElement).toBe(opener);
  });
});
