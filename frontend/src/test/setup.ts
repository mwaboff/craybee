import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll } from "vitest";

import { resetFixtures } from "./fixtures/llmServers";
import { server } from "./server";

beforeAll(async () => {
  server.listen({ onUnhandledRequest: "error" });

  // Relative-URL fetch shim: the app's fetch wrapper calls fetch("/api/v1/...")
  // and Node's fetch rejects relative URLs. Installed *after* server.listen()
  // so it wraps msw's interceptor -- installing it before would mean msw's
  // interceptor sees the relative URL first and throws when it builds a
  // `new Request(relativeUrl)`.
  const originalFetch = globalThis.fetch;
  globalThis.fetch = ((input: RequestInfo | URL, init?: RequestInit) => {
    if (typeof input === "string" && input.startsWith("/")) {
      const resolved = new URL(input, window.location.origin).toString();
      return originalFetch(resolved, init);
    }
    return originalFetch(input, init);
  }) as typeof fetch;

  // motion's reduced-motion checks call matchMedia; jsdom doesn't implement it.
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener() {},
      removeEventListener() {},
      addListener() {},
      removeListener() {},
      dispatchEvent() {
        return false;
      },
    }),
  });

  // jsdom doesn't implement ResizeObserver; useStickToBottom needs one to
  // exist. Assigned directly (not vi.stubGlobal) so per-test
  // vi.unstubAllGlobals() calls elsewhere (e.g. WebSocket stubs) don't wipe it.
  class FakeResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  globalThis.ResizeObserver = FakeResizeObserver as unknown as typeof ResizeObserver;

  // Skip AnimatePresence exit animations in jsdom so unmounts are synchronous.
  try {
    const motionReact = await import("motion/react");
    if ("MotionGlobalConfig" in motionReact) {
      (motionReact as unknown as { MotionGlobalConfig: { skipAnimations: boolean } }).MotionGlobalConfig.skipAnimations =
        true;
    }
  } catch {
    // motion/react not resolvable in this environment; animations will just run.
  }
});

afterEach(() => {
  server.resetHandlers();
  resetFixtures();
  cleanup();
});

afterAll(() => {
  server.close();
});
