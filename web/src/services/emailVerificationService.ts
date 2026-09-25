/**
 * Email verification (todo 446) — the backend half of the /verify-email page.
 *
 * Confirming sends the signed key from the email link and NOTHING else: no
 * cookies, no CSRF token. The key names the address, so whoever is signed in
 * on this browser never changes which account it verifies. Resending acts on
 * the signed-in user, so it goes through the shared `apiClient` (cookies +
 * CSRF).
 */
import apiClient from '../utils/httpClient';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/** Why a confirm failed: a bad/expired/used link, or we could not tell. */
export type VerificationFailure = 'invalid' | 'error';

export class VerificationError extends Error {
  readonly reason: VerificationFailure;

  constructor(reason: VerificationFailure, message: string) {
    super(message);
    this.name = 'VerificationError';
    this.reason = reason;
  }
}

/** Confirm the email address the key names. */
export async function confirmEmailVerification(key: string): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}/api/v1/auth/verify-email/`, {
      method: 'POST',
      credentials: 'omit',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({ key }),
    });
  } catch {
    throw new VerificationError('error', 'Could not reach the server.');
  }
  if (response.ok) return;
  if (response.status === 400) {
    throw new VerificationError('invalid', 'This link is invalid, expired or already used.');
  }
  throw new VerificationError('error', `Request failed (HTTP ${response.status})`);
}

export interface ResendResult {
  verified: boolean;
  sent: boolean;
}

/** Email the signed-in user a fresh link. `verified` means there is nothing to do. */
export async function resendVerificationEmail(): Promise<ResendResult> {
  const response = await apiClient.post<ResendResult>('/api/v1/auth/verify-email/resend/');
  return response.data;
}
