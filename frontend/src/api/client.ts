/**
 * Thin fetch wrapper. Paths are relative on purpose: same-origin in prod,
 * proxied by Vite in dev, so no base-URL configuration exists to drift.
 */

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
    readonly fieldErrors: Record<string, string> = {},
  ) {
    super(message);
  }
}

type PydanticErrorItem = { loc: (string | number)[]; msg: string };

/**
 * Accepts both backend error shapes: a plain `{detail: string}` and a
 * Pydantic validation body `{detail: [{loc, msg}, ...]}`. For list items,
 * a leading "body" segment in `loc` is stripped; if a string segment
 * remains, its `msg` becomes a field error (first-wins); otherwise the
 * `msg` is collected into the overall message.
 */
export function parseErrorBody(
  body: unknown,
  fallback: string,
): { message: string; fieldErrors: Record<string, string> } {
  if (body === null || typeof body !== "object") {
    return { message: fallback, fieldErrors: {} };
  }
  const detail = (body as { detail?: unknown }).detail;

  if (typeof detail === "string") {
    return { message: detail, fieldErrors: {} };
  }

  if (Array.isArray(detail)) {
    const fieldErrors: Record<string, string> = {};
    const messages: string[] = [];
    for (const item of detail) {
      if (
        typeof item !== "object" ||
        item === null ||
        !Array.isArray((item as PydanticErrorItem).loc) ||
        typeof (item as PydanticErrorItem).msg !== "string"
      ) {
        continue;
      }
      const { loc, msg } = item as PydanticErrorItem;
      const rest = loc[0] === "body" ? loc.slice(1) : loc;
      const field = rest[0];
      if (typeof field === "string") {
        if (!(field in fieldErrors)) {
          fieldErrors[field] = msg;
        }
      } else {
        messages.push(msg);
      }
    }
    const message = messages.length > 0 ? messages.join("; ") : fallback;
    return { message, fieldErrors };
  }

  return { message: fallback, fieldErrors: {} };
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const { message, fieldErrors } = parseErrorBody(body, response.statusText || "Request failed");
    throw new ApiError(response.status, message, fieldErrors);
  }
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
}

/** Build a same-origin WebSocket URL, honouring https -> wss. */
export function wsUrl(path: string): string {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}${path}`;
}
