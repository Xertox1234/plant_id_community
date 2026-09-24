/**
 * Profile API Service — read and edit the signed-in user's own profile
 * (web dead-code audit M3: the backend endpoint existed, only mobile used it).
 *
 * Goes through the shared `apiClient` (todo 407 item 9), so it inherits the
 * client's cookie credentials, X-Request-ID, CSRF header on mutating requests
 * only, and its one-shot refresh-and-retry when a stale CSRF token gets a 403.
 * A bodyless GET carries no `Content-Type` (axios's xhr adapter drops it).
 */
import axios from 'axios';
import apiClient from '../utils/httpClient';
import type { ProfileUpdate, UserProfile } from '../types/auth';

const AUTH_BASE = '/api/v1/auth';

/**
 * Turn a DRF error body into one readable message. Validation errors arrive
 * either flattened (`{message}`) or as a field map (`{website: ["Enter a valid URL."]}`).
 */
function errorMessage(body: unknown, status: number): string {
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
 * Re-throw an HTTP failure as a plain `Error` carrying the server's readable
 * message — an AxiosError's own message is "Request failed with status code
 * 400", which is not what ProfilePage should show. Anything without a
 * response (network, timeout) propagates unchanged.
 */
function toProfileError(error: unknown): unknown {
  if (axios.isAxiosError(error) && error.response) {
    return new Error(errorMessage(error.response.data, error.response.status), { cause: error });
  }
  return error;
}

export async function fetchProfile(): Promise<UserProfile> {
  try {
    const response = await apiClient.get<UserProfile>(`${AUTH_BASE}/user/`);
    return response.data;
  } catch (error) {
    throw toProfileError(error);
  }
}

export async function updateProfile(changes: ProfileUpdate): Promise<UserProfile> {
  try {
    const response = await apiClient.patch<{ message: string; user: UserProfile }>(
      `${AUTH_BASE}/user/update/`,
      changes
    );
    return response.data.user;
  } catch (error) {
    throw toProfileError(error);
  }
}
