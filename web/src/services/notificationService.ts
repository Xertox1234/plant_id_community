/**
 * Notification API Service — translation layer for the forum notification
 * endpoints (todo 253 slice 1, audit C2).
 *
 * Goes through the shared `apiClient` (todo 407 item 9), so it inherits the
 * client's cookie credentials, X-Request-ID, CSRF header on mutating requests
 * only, and its one-shot refresh-and-retry when a stale CSRF token gets a 403.
 * A bodyless GET carries no `Content-Type` (axios's xhr adapter drops it).
 */
import apiClient from '../utils/httpClient';
import { toHttpError } from '../utils/httpError';
import type {
  ForumNotification,
  MarkReadResponse,
  NotificationListResponse,
  UnreadCountResponse,
} from '../types/notifications';

const FORUM_BASE = '/api/v1/forum';

/**
 * One request through `apiClient`. A failure is re-thrown through the shared
 * `toHttpError` (todo 434) as a plain `Error` carrying the server's
 * `message`/`detail`. `quietErrors` keeps a failure out of Sentry — for the
 * background poll only (see fetchUnreadCount).
 */
async function request<T>(
  method: 'get' | 'post',
  url: string,
  data?: Record<string, unknown>,
  quietErrors = false
): Promise<T> {
  try {
    const response = await apiClient.request<T>({ method, url, data, quietErrors });
    if (response.status === 204) return undefined as T;
    // axios resolves a non-JSON body (a CDN challenge page, an SPA fallback)
    // as a string; fetch's response.json() rejected it. Keep rejecting, or
    // the unread badge renders `undefined` (PR #817 review).
    if (typeof response.data !== 'object' || response.data === null) {
      throw new Error('Request failed');
    }
    return response.data;
  } catch (error) {
    throw toHttpError(error);
  }
}

/**
 * List notifications, newest first. Pass an absolute cursor URL (from a prior
 * response's `next`) to fetch a later page — DRF cursor URLs are absolute and
 * must be fetched verbatim, never re-prefixed with FORUM_BASE (axios applies
 * `baseURL` only to relative URLs).
 */
export async function fetchNotifications(cursorUrl?: string): Promise<NotificationListResponse> {
  return request<NotificationListResponse>('get', cursorUrl || `${FORUM_BASE}/notifications/`);
}

/**
 * The unread badge count. Polled every 30s per tab (UnreadNotificationsContext),
 * and the poll just retries on the next tick, so a failure is a breadcrumb, not
 * a Sentry event: a backend blip or an expired cookie would otherwise raise one
 * event per tab every 30s (todo 434).
 */
export async function fetchUnreadCount(): Promise<number> {
  const data = await request<UnreadCountResponse>(
    'get',
    `${FORUM_BASE}/notifications/unread-count/`,
    undefined,
    true
  );
  return data.count;
}

/** Mark specific notifications read, or ALL unread ones when `ids` is omitted. */
export async function markNotificationsRead(ids?: number[]): Promise<number> {
  const data = await request<MarkReadResponse>(
    'post',
    `${FORUM_BASE}/notifications/mark-read/`,
    ids ? { ids } : {}
  );
  return data.updated;
}

export type { ForumNotification };
