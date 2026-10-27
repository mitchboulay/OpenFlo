/**
 * Typed JSON fetch wrapper for the OpenFLO backend (same origin; the session
 * cookie rides along, the UI never holds a token). Every failure surfaces as an
 * `ApiError` so callers handle exactly one error type.
 */

/** Error body of `/api/v1` (AD-10): `{code, message, detail?}`. */
export interface ApiErrorBody {
  code: string;
  message: string;
  detail?: unknown;
}

/** Client-side failure codes (status 0: no HTTP response was received). */
export const CLIENT_ERROR_CODES = {
  network: 'NETWORK_ERROR',
  timeout: 'TIMEOUT',
  invalidResponse: 'INVALID_RESPONSE',
  http: 'HTTP_ERROR',
} as const;

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly detail: unknown;

  constructor(status: number, code: string, message: string, detail?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.detail = detail;
  }
}

export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

export interface ApiRequestOptions {
  method?: HttpMethod;
  /** Serialized as JSON. */
  body?: unknown;
  signal?: AbortSignal;
  /** Defaults to `DEFAULT_TIMEOUT_MS`. */
  timeoutMs?: number;
  /** Browser HTTP cache mode, e.g. `no-cache` to revalidate a response the server marks cacheable. */
  cache?: RequestCache;
}

export const DEFAULT_TIMEOUT_MS = 15_000;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/** Maps any error body (the v1 shape, FastAPI's legacy `{detail}`, or none) to an ApiError. */
export function toApiError(status: number, statusText: string, body: unknown): ApiError {
  if (isRecord(body)) {
    if (typeof body.code === 'string' && typeof body.message === 'string') {
      return new ApiError(status, body.code, body.message, body.detail);
    }
    if (typeof body.detail === 'string') {
      return new ApiError(status, CLIENT_ERROR_CODES.http, body.detail);
    }
    if (body.detail !== undefined) {
      return new ApiError(status, CLIENT_ERROR_CODES.http, 'The request was not accepted.', body.detail);
    }
  }
  return new ApiError(status, CLIENT_ERROR_CODES.http, statusText || `Request failed (${status}).`);
}

function parseJson(text: string): { ok: true; value: unknown } | { ok: false } {
  if (text === '') return { ok: true, value: undefined };
  try {
    return { ok: true, value: JSON.parse(text) as unknown };
  } catch {
    return { ok: false };
  }
}

/**
 * Sends a JSON request and returns the parsed response body as `T`.
 * `T` comes from the generated contract (`schema.d.ts`); the server is the validator.
 */
export async function apiRequest<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  const { method = 'GET', body, signal, timeoutMs = DEFAULT_TIMEOUT_MS, cache } = options;
  const timeout = AbortSignal.timeout(timeoutMs);
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (body !== undefined) headers['Content-Type'] = 'application/json';

  let response: Response;
  try {
    response = await fetch(new URL(path, window.location.origin), {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      credentials: 'same-origin',
      cache,
      signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
    });
  } catch (error) {
    if (signal?.aborted) throw error; // caller cancelled (e.g. React Query); not an API failure
    if (timeout.aborted) {
      throw new ApiError(0, CLIENT_ERROR_CODES.timeout, 'The server took too long to respond.');
    }
    throw new ApiError(0, CLIENT_ERROR_CODES.network, 'Could not reach the server.');
  }

  const parsed = parseJson(await response.text());
  if (!response.ok) {
    throw toApiError(response.status, response.statusText, parsed.ok ? parsed.value : undefined);
  }
  if (!parsed.ok) {
    throw new ApiError(response.status, CLIENT_ERROR_CODES.invalidResponse, 'The server sent an unreadable response.');
  }
  return parsed.value as T;
}
