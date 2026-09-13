import type { RunEvent } from "@/types/run";

/**
 * Minimal WebSocket stand-in for tests. Install with
 * `vi.stubGlobal("WebSocket", FakeWebSocket)`, then drive the socket
 * `useRunStream` opened via `FakeWebSocket.latestSocket()`.
 *
 * Real `onopen`/`onmessage`/`onclose` never fire on their own -- call
 * `open()` / `emit(event)` to trigger them explicitly.
 */
export class FakeWebSocket {
  static instances: FakeWebSocket[] = [];

  onopen: (() => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  closed = false;

  constructor(readonly url: string) {
    FakeWebSocket.instances.push(this);
  }

  open() {
    this.onopen?.();
  }

  emit(event: RunEvent) {
    this.onmessage?.({ data: JSON.stringify(event) } as MessageEvent);
  }

  close() {
    this.closed = true;
    this.onclose?.({ code: 1000 } as CloseEvent);
  }

  static reset() {
    FakeWebSocket.instances = [];
  }

  static latestSocket(): FakeWebSocket | undefined {
    return FakeWebSocket.instances[FakeWebSocket.instances.length - 1];
  }
}
