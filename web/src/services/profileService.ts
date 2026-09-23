/**
 * Profile API Service — read and edit the signed-in user's own profile
 * (web dead-code audit M3: the backend endpoint existed, only mobile used it).
 *
 * Cookie-based JWT auth with CSRF on mutating requests (same pattern as
 * notificationService.ts).
 */
import { getCsrfToken } from '../utils/csrf';
import type { ProfileUpdate, UserProfile } from '../types/auth';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const AUTH_BASE = `${API_URL}/api/v1/auth`;

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

async function authenticatedFetch<T>(url: string, options: RequestInit = {}): Promise<T> {
  const csrfToken = await getCsrfToken();
  const response = await fetch(url, {
    ...options,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
      ...(csrfToken && { 'X-CSRFToken': csrfToken }),
      ...options.headers,
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(errorMessage(body, response.status));
  }
  return response.json();
}

export async function fetchProfile(): Promise<UserProfile> {
  return authenticatedFetch<UserProfile>(`${AUTH_BASE}/user/`);
}

export async function updateProfile(changes: ProfileUpdate): Promise<UserProfile> {
  const data = await authenticatedFetch<{ message: string; user: UserProfile }>(
    `${AUTH_BASE}/user/update/`,
    { method: 'PATCH', body: JSON.stringify(changes) }
  );
  return data.user;
}
