/**
 * Direct-message API service (todo 339) — the forum's private conversations.
 *
 * Its own module rather than another 100 lines on forumService.ts, in the
 * same shape as notificationService.ts. Cookie-based JWT auth with CSRF on
 * mutating requests; failures throw `ForumApiError` so callers can branch on
 * the HTTP status (403 = blocked, 400 = spam/empty) instead of sniffing text.
 */
import { getCsrfToken } from '../utils/csrf';
import { ForumApiError } from './forumService';
import type { Conversation, DirectMessage, DirectMessageCursorPage } from '../types/forum';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const FORUM_BASE = `${API_URL}/api/v1/forum`;

/** Backend cap on one message body; the composer shows it and `maxLength`s to it. */
export const MESSAGE_MAX_LENGTH = 4000;

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
    throw new ForumApiError(
      error.message || error.detail || `HTTP ${response.status}`,
      response.status
    );
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}

/**
 * The inbox, most recent activity first. Pass a prior page's `next` to fetch
 * the one after it — DRF cursor URLs are absolute and fetched verbatim.
 */
export async function fetchConversations(
  cursorUrl?: string
): Promise<DirectMessageCursorPage<Conversation>> {
  return authenticatedFetch<DirectMessageCursorPage<Conversation>>(
    cursorUrl || `${FORUM_BASE}/conversations/`
  );
}

/** Number of conversations with unread messages — the inbox badge. */
export async function fetchUnreadConversationCount(): Promise<number> {
  const data = await authenticatedFetch<{ count: number }>(
    `${FORUM_BASE}/conversations/unread-count/`
  );
  return data.count;
}

/**
 * The viewer's conversation with `username`, or null when there is none yet.
 * The backend also answers 404 for an unknown member and when either side has
 * blocked the other — all three mean "no thread to show"; the send path is
 * where the real reason surfaces (404 / 403 respectively).
 */
export async function fetchConversationWith(username: string): Promise<Conversation | null> {
  try {
    return await authenticatedFetch<Conversation>(
      `${FORUM_BASE}/conversations/with/${encodeURIComponent(username)}/`
    );
  } catch (err) {
    if (err instanceof ForumApiError && err.status === 404) return null;
    throw err;
  }
}

/**
 * One page of a conversation's messages, NEWEST first (page older via
 * `next`). Reading any page marks the conversation read server-side, so the
 * caller should refresh the unread badge afterwards.
 */
export async function fetchMessages(
  conversationId: number,
  cursorUrl?: string
): Promise<DirectMessageCursorPage<DirectMessage>> {
  return authenticatedFetch<DirectMessageCursorPage<DirectMessage>>(
    cursorUrl || `${FORUM_BASE}/conversations/${conversationId}/messages/`
  );
}

/**
 * Send a plain-text message to `username`; creates the conversation on first
 * send. Throws ForumApiError 403 when either side has blocked the other, 400
 * for an empty/spam body (message carries the reason), 404 for an unknown member.
 */
export async function sendMessage(username: string, body: string): Promise<DirectMessage> {
  return authenticatedFetch<DirectMessage>(
    `${FORUM_BASE}/users/${encodeURIComponent(username)}/messages/`,
    { method: 'POST', body: JSON.stringify({ body }) }
  );
}

/** Report someone else's message for moderator review (400 for your own). */
export async function reportMessage(
  messageId: number,
  reason: string,
  detail?: string
): Promise<void> {
  await authenticatedFetch<{ reported: boolean }>(`${FORUM_BASE}/messages/${messageId}/report/`, {
    method: 'POST',
    body: JSON.stringify({ reason, detail: detail ?? '' }),
  });
}
