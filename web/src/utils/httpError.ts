/**
 * Turn an `apiClient` HTTP or connection failure into a plain `Error` whose
 * message is fit to show a user (todo 434). Shared by every service on
 * `apiClient`, so one wording covers them all. A cancellation, a non-axios
 * error, and any other response-less axios error (`ERR_INVALID_URL`, a
 * code-less interceptor rejection — client bugs) pass through unchanged,
 * axios's own message and all (todo 489).
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
 * The axios codes that mean the request never got an answer: the network
 * failed (`ERR_NETWORK`) or it timed out (`ECONNABORTED`, or `ETIMEDOUT` with
 * `transitional.clarifyTimeoutError`). Only these are connection problems
 * (todo 489).
 *
 * These are the browser (XHR/fetch adapter) codes. Node's http adapter
 * reports a dead server as `ECONNREFUSED`/`ENOTFOUND`, which would pass
 * through untranslated; the web client only ever runs in a browser, so they
 * are left out on purpose (todo 510).
 */
const CONNECTION_ERROR_CODES: ReadonlySet<string> = new Set([
  'ERR_NETWORK',
  'ECONNABORTED',
  'ETIMEDOUT',
]);

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
 * A cancellation, anything that is not an axios error, and any other
 * response-less axios error (`ERR_INVALID_URL`, `ERR_BAD_OPTION_VALUE`, an
 * interceptor rejection) is returned as is: those are client bugs, and
 * calling them a connection problem would hide them (todo 489).
 */
export function toHttpError(error: unknown): unknown {
  if (!axios.isAxiosError(error) || axios.isCancel(error)) return error;
  if (error.response) {
    return new Error(httpErrorMessage(error.response.data, error.response.status), {
      cause: error,
    });
  }
  if (error.code && CONNECTION_ERROR_CODES.has(error.code)) {
    return new Error(NETWORK_ERROR_MESSAGE, { cause: error });
  }
  return error;
}
