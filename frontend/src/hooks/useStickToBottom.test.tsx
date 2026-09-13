import { act, renderHook } from "@testing-library/react";
import { createRef } from "react";
import { describe, expect, it } from "vitest";

import { useStickToBottom } from "./useStickToBottom";

/**
 * jsdom never computes layout, so scrollHeight/clientHeight/scrollTop are
 * always 0. Define them explicitly to simulate a scrolled container.
 */
function makeScroller({
  scrollHeight,
  clientHeight,
  scrollTop,
}: {
  scrollHeight: number;
  clientHeight: number;
  scrollTop: number;
}) {
  const scroller = document.createElement("div");
  const content = document.createElement("div");
  scroller.appendChild(content);
  document.body.appendChild(scroller);

  Object.defineProperty(scroller, "scrollHeight", { value: scrollHeight, configurable: true });
  Object.defineProperty(scroller, "clientHeight", { value: clientHeight, configurable: true });
  let top = scrollTop;
  Object.defineProperty(scroller, "scrollTop", {
    get: () => top,
    set: (value) => {
      top = value;
    },
    configurable: true,
  });

  return { scroller, content };
}

describe("useStickToBottom", () => {
  it("reports at bottom when within the threshold", () => {
    const { scroller } = makeScroller({ scrollHeight: 500, clientHeight: 300, scrollTop: 200 });
    const ref = createRef<HTMLElement>();
    (ref as { current: HTMLElement }).current = scroller;

    const { result } = renderHook(() => useStickToBottom(ref, 24));

    expect(result.current.isAtBottom).toBe(true);
  });

  it("reports not at bottom when scrolled away, and scrollToBottom re-engages", () => {
    const { scroller } = makeScroller({ scrollHeight: 500, clientHeight: 300, scrollTop: 0 });
    const ref = createRef<HTMLElement>();
    (ref as { current: HTMLElement }).current = scroller;

    const { result } = renderHook(() => useStickToBottom(ref, 24));

    expect(result.current.isAtBottom).toBe(false);

    act(() => {
      result.current.scrollToBottom();
    });

    expect(scroller.scrollTop).toBe(500);
    expect(result.current.isAtBottom).toBe(true);
  });

  it("updates isAtBottom on scroll events", () => {
    const { scroller } = makeScroller({ scrollHeight: 500, clientHeight: 300, scrollTop: 0 });
    const ref = createRef<HTMLElement>();
    (ref as { current: HTMLElement }).current = scroller;

    const { result } = renderHook(() => useStickToBottom(ref, 24));
    expect(result.current.isAtBottom).toBe(false);

    Object.defineProperty(scroller, "scrollTop", { value: 200, configurable: true });
    act(() => {
      scroller.dispatchEvent(new Event("scroll"));
    });

    expect(result.current.isAtBottom).toBe(true);
  });
});
