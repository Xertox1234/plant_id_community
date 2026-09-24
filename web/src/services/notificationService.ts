/**
 * Notification API Service — translation layer for the forum notification
 * endpoints (todo 253 slice 1, audit C2).
 *
 * Goes through the shared `apiClient` (todo 407 item 9), so it inherits the
 * client's cookie credentials, X-Request-ID, CSRF header on mutating requests
 * only, and its one-shot refresh-and-retry when a stale CSRF token gets a 403.
 * A bodyless GET carries no `Content-Type` (axios's xhr adapter drops it).
 */
import axios from 'axios';
import apiClient from '../utils/httpClient';
import type {
  ForumNotification,
  MarkReadResponse,
  NotificationListResponse,
  UnreadCountResponse,
} from '../types/notifications';

const FORUM_BASE = '/api/v1/forum';

/**
 * Re-throw an HTTP failure as a plain `Error` carrying the server's
 * `message`/`detail` (falling back to `HTTP <status>`), the shape callers
 * have always received. Anything without a response propagates unchanged.
 */
function toNotificationError(error: unknown): unknown {
  if (axios.isAxiosError(error) && error.response) {
    const { data, status } = error.response;
    const body: { message?: unknown; detail?: unknown } =
      data && typeof data === 'object' ? data : { message: 'Request failed' };
    const message =
      (typeof body.message === 'string' && body.message) ||
      (typeof body.detail === 'string' && body.detail) ||
      `HTTP ${status}`;
    return new Error(message, { cause: error });
  }
  return error;
}

async function request<T>(
  method: 'get' | 'post',
  url: string,
  data?: Record<string, unknown>
): Promise<T> {
  try {
    const response = await apiClient.request<T>({ method, url, data });
    if (response.status === 204) return undefined as T;
    return response.data;
  } catch (error) {
    throw toNotificationError(error);
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

export async function fetchUnreadCount(): Promise<number> {
  const data = await request<UnreadCountResponse>(
    'get',
    `${FORUM_BASE}/notifications/unread-count/`
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
