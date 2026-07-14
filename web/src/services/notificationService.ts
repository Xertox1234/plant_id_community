/**
 * Notification API Service — translation layer for the forum notification
 * endpoints (todo 253 slice 1, audit C2).
 *
 * Cookie-based JWT auth with CSRF on mutating requests (same pattern as
 * forumService.ts).
 */
import { getCsrfToken } from '../utils/csrf';
import type {
  ForumNotification,
  MarkReadResponse,
  NotificationListResponse,
  UnreadCountResponse,
} from '../types/notifications';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const FORUM_BASE = `${API_URL}/api/v1/forum`;

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
    const error = await response.json().catch(() => ({ message: 'Request failed' }));
    throw new Error(error.message || error.detail || `HTTP ${response.status}`);
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}

/**
 * List notifications, newest first. Pass an absolute cursor URL (from a prior
 * response's `next`) to fetch a later page — DRF cursor URLs are absolute and
 * must be fetched verbatim, never re-prefixed with FORUM_BASE.
 */
export async function fetchNotifications(cursorUrl?: string): Promise<NotificationListResponse> {
  return authenticatedFetch<NotificationListResponse>(cursorUrl || `${FORUM_BASE}/notifications/`);
}

export async function fetchUnreadCount(): Promise<number> {
  const data = await authenticatedFetch<UnreadCountResponse>(
    `${FORUM_BASE}/notifications/unread-count/`
  );
  return data.count;
}

/** Mark specific notifications read, or ALL unread ones when `ids` is omitted. */
export async function markNotificationsRead(ids?: number[]): Promise<number> {
  const data = await authenticatedFetch<MarkReadResponse>(
    `${FORUM_BASE}/notifications/mark-read/`,
    {
      method: 'POST',
      body: JSON.stringify(ids ? { ids } : {}),
    }
  );
  return data.updated;
}

export type { ForumNotification };
