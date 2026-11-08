/**
 * Account deletion (Plan B) — the backend half of Settings > Delete account and
 * the public /delete-account pages.
 *
 * Both endpoints are public: the emailed signed token is the only credential for
 * `confirm`, and `request` always answers 200 so it cannot reveal whether an
 * address has an account. Neither needs a CSRF token. `confirm` sends cookies so
 * the browser applies the server's cookie clearing on success.
 */
import { API_ORIGIN } from '@/config/api';

const BASE = `${API_ORIGIN}/api/v1/auth/account/delete`;

/**
 * - `rate_limited`: 429 on request;
 * - `link_invalid`: the emailed link expired or was already used;
 * - `contact_support`: the account cannot be self-deleted;
 * - `error`: we could not tell (network, 5xx, unreadable body).
 */
export type AccountDeletionErrorCode =
  'rate_limited' | 'link_invalid' | 'contact_support' | 'error';

export class AccountDeletionError extends Error {
  readonly code: AccountDeletionErrorCode;

  constructor(code: AccountDeletionErrorCode, message: string) {
    super(message);
    this.name = 'AccountDeletionError';
    this.code = code;
  }
}

async function post(
  path: string,
  body: Record<string, string>,
  credentials: RequestCredentials
): Promise<{ response: Response; json: Record<string, unknown> | null }> {
  let response: Response;
  try {
    response = await fetch(`${BASE}/${path}/`, {
      method: 'POST',
      credentials,
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify(body),
    });
  } catch {
    throw new AccountDeletionError('error', 'Could not reach the server.');
  }
  const parsed: unknown = await response.json().catch(() => null);
  const json = parsed && typeof parsed === 'object' ? (parsed as Record<string, unknown>) : null;
  return { response, json };
}

/** Email a deletion link to `email` (always "sent" unless rate-limited or down). */
export async function requestAccountDeletion(email: string): Promise<void> {
  const { response } = await post('request', { email }, 'omit');
  if (response.ok) return;
  if (response.status === 429) {
    throw new AccountDeletionError('rate_limited', 'Too many requests, try again later.');
  }
  throw new AccountDeletionError('error', 'Something went wrong. Please try again.');
}

/** Schedule the deletion the emailed link authorises. */
export async function confirmAccountDeletion(token: string): Promise<'scheduled'> {
  const { response, json } = await post('confirm', { token }, 'include');
  if (response.status === 202 && json?.status === 'scheduled') return 'scheduled';
  const code = json?.code;
  const message = typeof json?.error === 'string' ? json.error : null;
  if (code === 'link_invalid' || code === 'contact_support') {
    throw new AccountDeletionError(code, message ?? 'This request could not be completed.');
  }
  throw new AccountDeletionError('error', 'Something went wrong. Please try again.');
}
