/**
 * `fetch` with the CSRF token, and ONE retry when the token went stale
 * (audit F143).
 *
 * The token is cached in memory (utils/csrf). A login in another tab rotates
 * the CSRF cookie, so every write from this tab then 403s with
 * "CSRF Failed: ..." until a reload. On exactly that 403, this refreshes the
 * token from `/api/csrf/` and sends the request once more with the same init:
 * the same body and the same headers, so a write's Idempotency-Key is reused
 * and the retry can never become a second post.
 *
 * Any other 403 (a block, a permission refusal) is returned untouched, so the
 * caller still shows its own message. Returns the Response, never throws on a
 * status: each service keeps its own error class.
 */
import { getCsrfToken, refreshCsrfToken } from './csrf';

const CSRF_FAILED = 'CSRF Failed';

/**
 * True for the backend's CSRF refusal: `CookieJWTAuthentication.enforce_csrf`
 * raises `PermissionDenied("CSRF Failed: <reason>")`, which the envelope in
 * apps/core/exceptions.py carries as `message` (raw DRF: `detail`). Its `code`
 * is `permission_denied`, the same as a blocked 403, so only the text tells
 * them apart. Takes a parsed body or an error message.
 */
export function isCsrfFailure(value: unknown): boolean {
  if (typeof value === 'string') return value.includes(CSRF_FAILED);
  if (typeof value !== 'object' || value === null) return false;
  const { message, detail } = value as { message?: unknown; detail?: unknown };
  return [message, detail].some((v) => typeof v === 'string' && v.includes(CSRF_FAILED));
}

function withToken(init: RequestInit, token: string | null): RequestInit {
  return {
    ...init,
    credentials: 'include',
    headers: {
      ...(init.headers as Record<string, string> | undefined),
      ...(token && { 'X-CSRFToken': token }),
    },
  };
}

export async function csrfFetch(url: string, init: RequestInit = {}): Promise<Response> {
  const response = await fetch(url, withToken(init, await getCsrfToken()));
  if (response.status !== 403) return response;

  // Peek without consuming the caller's body.
  const peek = typeof response.clone === 'function' ? response.clone() : response;
  const body: unknown = await peek.json().catch(() => null);
  if (!isCsrfFailure(body)) return response;

  const fresh = await refreshCsrfToken();
  if (!fresh) return response;
  return fetch(url, withToken(init, fresh));
}
