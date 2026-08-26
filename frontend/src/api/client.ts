/**
 * Thin fetch wrapper. Paths are relative on purpose: same-origin in prod,
 * proxied by Vite in dev, so no base-URL configuration exists to drift.
 */

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });

  if (!response.ok) {
    const detail = await response.json().catch(() => ({ detail: response.statusText }));
    throw new ApiError(response.status, detail.detail ?? "Request failed");
  }
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
}

/** Build a same-origin WebSocket URL, honouring https -> wss. */
export function wsUrl(path: string): string {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}${path}`;
}
