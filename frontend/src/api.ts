export const API_BASE: string = import.meta.env.VITE_API_URL ?? "";

export const CONNECTION_ERROR = "Request failed. Check the API connection.";

// An authenticated fetch. `accessToken` overrides the bound token, which
// bootstrap() needs because it runs before the token has been stored in state.
export type ApiRequest = (
  path: string,
  options?: RequestInit,
  accessToken?: string
) => Promise<Response>;

export function makeRequest(token: string): ApiRequest {
  return async (path, options = {}, accessToken = token) => {
    const requestHeaders = new Headers(options.headers ?? {});
    if (accessToken) requestHeaders.set("Authorization", `Bearer ${accessToken}`);
    return fetch(`${API_BASE}${path}`, { ...options, headers: requestHeaders });
  };
}

export function jsonBody(payload: unknown): Pick<RequestInit, "headers" | "body"> {
  return {
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  };
}

// A discriminated union so callers cannot read `body` as the success shape
// without first checking `ok`: on failure the body is only `unknown`.
export type ParsedResponse<T> =
  | { ok: true; status: number; body: T }
  | { ok: false; status: number; body: unknown; errorMessage: string };

// Parses a response body once (a non-JSON or empty body becomes {}) and, when
// the response was not ok, derives a human-readable message: a string `detail`
// (the usual FastAPI shape), a structured `{ message }` detail (the
// beta-readiness gate's 409), or `fallbackMessage`.
export async function parseResponse<T = unknown>(
  res: Response,
  fallbackMessage: string
): Promise<ParsedResponse<T>> {
  const body: unknown = await res.json().catch(() => ({}));
  if (res.ok) return { ok: true, status: res.status, body: body as T };
  const detail = (body as { detail?: string | { message?: string } } | null)?.detail;
  const errorMessage = (typeof detail === "string" ? detail : detail?.message) ?? fallbackMessage;
  return { ok: false, status: res.status, body, errorMessage };
}
