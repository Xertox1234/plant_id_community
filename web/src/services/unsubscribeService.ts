/**
 * Email unsubscribe (todo 408) — the backend half of the /unsubscribe page.
 *
 * The signed token from the email link is the ONLY credential: requests go
 * out without cookies or a CSRF token, so whoever is signed in on this
 * browser never changes which account the link acts on.
 */

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const UNSUBSCRIBE_BASE = `${API_URL}/api/v1/auth/unsubscribe`;

export interface EmailListState {
  list: string;
  label: string;
  subscribed: boolean;
}

/** Why a link cannot act: forged/unknown, too old, or we could not tell. */
export type UnsubscribeFailure = 'invalid' | 'expired' | 'error';

export class UnsubscribeError extends Error {
  readonly reason: UnsubscribeFailure;

  constructor(reason: UnsubscribeFailure, message: string) {
    super(message);
    this.name = 'UnsubscribeError';
    this.reason = reason;
  }
}

function isListState(body: unknown): body is EmailListState {
  if (!body || typeof body !== 'object') return false;
  const record = body as Record<string, unknown>;
  return (
    typeof record.list === 'string' &&
    typeof record.label === 'string' &&
    typeof record.subscribed === 'boolean'
  );
}

async function post(url: string, token: string): Promise<EmailListState> {
  let response: Response;
  try {
    response = await fetch(url, {
      method: 'POST',
      credentials: 'omit',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({ token }),
    });
  } catch {
    throw new UnsubscribeError('error', 'Could not reach the server.');
  }
  const body: unknown = await response.json().catch(() => null);
  if (response.ok && isListState(body)) return body;
  const code = body && typeof body === 'object' ? (body as Record<string, unknown>).code : null;
  if (response.status === 400 && (code === 'invalid' || code === 'expired')) {
    throw new UnsubscribeError(code, code);
  }
  throw new UnsubscribeError('error', `Request failed (HTTP ${response.status})`);
}

/** Describe what the link unsubscribes from, without changing anything. */
export function checkUnsubscribe(token: string): Promise<EmailListState> {
  return post(`${UNSUBSCRIBE_BASE}/check/`, token);
}

/** Unsubscribe. Idempotent: a second call reports the same final state. */
export function confirmUnsubscribe(token: string): Promise<EmailListState> {
  return post(`${UNSUBSCRIBE_BASE}/`, token);
}
