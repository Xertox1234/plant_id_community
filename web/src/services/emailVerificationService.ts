/**
 * Email verification (todo 446) — the backend half of the /verify-email page.
 *
 * Confirming needs BOTH the signed key from the email link AND the session of
 * the account the key names, so it goes through the shared `apiClient`
 * (cookies + CSRF). With the key alone, a victim who clicked the link from
 * their inbox would verify an attacker's pre-registered account.
 */
import axios from 'axios';
import apiClient from '../utils/httpClient';

const AUTH_BASE = '/api/v1/auth';

/**
 * Why a confirm failed:
 * - `invalid`: a bad, expired or used link, or one for a different account;
 * - `signin`: no session;
 * - `error`: we could not tell.
 */
export type VerificationFailure = 'invalid' | 'signin' | 'error';

export class VerificationError extends Error {
  readonly reason: VerificationFailure;

  constructor(reason: VerificationFailure, message: string) {
    super(message);
    this.name = 'VerificationError';
    this.reason = reason;
  }
}

/** Confirm the signed-in user's email address with the key from their link. */
export async function confirmEmailVerification(key: string): Promise<void> {
  try {
    await apiClient.post(`${AUTH_BASE}/verify-email/`, { key });
  } catch (error) {
    const status = axios.isAxiosError(error) ? error.response?.status : undefined;
    if (status === 400) {
      throw new VerificationError('invalid', 'This link is invalid, expired or already used.');
    }
    if (status === 401 || status === 403) {
      throw new VerificationError('signin', 'Sign in to confirm your email.');
    }
    throw new VerificationError('error', 'Could not confirm your email.');
  }
}

export interface ResendResult {
  verified: boolean;
  sent: boolean;
}

/** Email the signed-in user a fresh link. `verified` means there is nothing to do. */
export async function resendVerificationEmail(): Promise<ResendResult> {
  const response = await apiClient.post<ResendResult>(`${AUTH_BASE}/verify-email/resend/`);
  return response.data;
}
