/**
 * Turn an `apiClient` failure into a plain `Error` whose message is fit to
 * show a user (todo 434). Shared by every service on `apiClient`, so one
 * wording covers them all.
 *
 * Kept out of `httpClient.ts` on purpose: tests that `vi.mock` that module
 * replace only its default export, and a named export would come back
 * undefined there.
 */
import axios from 'axios';

/** Shown for a network failure or timeout instead of axios's own text. */
export const NETWORK_ERROR_MESSAGE =
  'Could not reach the server. Check your connection and try again.';

/**
 * One readable message from a DRF error body. Errors arrive flattened
 * (`{message}`), as a bare `{detail}`, or as a field map
 * (`{website: ["Enter a valid URL."]}`); anything else falls back to the status.
 */
export function httpErrorMessage(body: unknown, status: number): string {
  if (body && typeof body === 'object') {
    const record = body as Record<string, unknown>;
    if (typeof record.message === 'string' && record.message) return record.message;
    if (typeof record.detail === 'string' && record.detail) return record.detail;
    for (const [field, value] of Object.entries(record)) {
      const first = Array.isArray(value) ? value[0] : value;
      if (typeof first === 'string' && first) return `${field.replace(/_/g, ' ')}: ${first}`;
    }
  }
  return `Request failed (HTTP ${status})`;
}

/**
 * Re-throwable form of an `apiClient` failure. An HTTP error carries the
 * server's message, not axios's "Request failed with status code 400". A
 * network error or timeout carries NETWORK_ERROR_MESSAGE, not "Network Error"
 * or "timeout of 30000ms exceeded". The original error is kept as `cause`.
 * A cancellation, or anything that is not an axios error, is returned as is.
 */
export function toHttpError(error: unknown): unknown {
  if (!axios.isAxiosError(error) || axios.isCancel(error)) return error;
  if (error.response) {
    return new Error(httpErrorMessage(error.response.data, error.response.status), {
      cause: error,
    });
  }
  return new Error(NETWORK_ERROR_MESSAGE, { cause: error });
}
