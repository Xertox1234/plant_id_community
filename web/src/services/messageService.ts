/**
 * Direct-message API service (todo 339) — the forum's private conversations,
 * direct and group (todo 350).
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

// Group conversations (todo 350) — mirrors the backend's DM_GROUP_MAX_PARTICIPANTS
// (8, including the creator) and the 80-char title column. The picker enforces
// the OTHERS range client-side so the common mistakes never cost a request;
// the server re-checks all of it.
export const GROUP_TITLE_MAX_LENGTH = 80;
export const GROUP_MAX_PARTICIPANTS = 8;
export const GROUP_MIN_OTHERS = 2;
export const GROUP_MAX_OTHERS = GROUP_MAX_PARTICIPANTS - 1;

/**
 * Integer seconds from a `Retry-After` header, or null. Only the delta form
 * is read (the HTTP-date form is legal but the API never sends it); the
 * `headers?.get?.` guard keeps hand-rolled test responses without a
 * `Headers` object from throwing inside the error path.
 */
function readRetryAfter(response: Response): number | null {
  const raw = response.headers?.get?.('Retry-After');
  if (!raw || !/^\d+$/.test(raw.trim())) return null;
  return Number.parseInt(raw, 10);
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
    const error = await response.json().catch(() => ({ message: 'Request failed' }));
    throw new ForumApiError(
      error.message || error.detail || `HTTP ${response.status}`,
      response.status,
      response.status === 429 ? readRetryAfter(response) : null
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

/**
 * The inbox row for one conversation id (any kind), or null on 404. The API
 * answers 404 alike for a non-participant, a removed member, and a blocked
 * direct pair — a stranger gets no signal the id exists — so null means "the
 * viewer cannot see this conversation", never "not yet" (unlike
 * `fetchConversationWith`). Every other failure is rethrown with its status.
 */
export async function fetchConversation(conversationId: number): Promise<Conversation | null> {
  try {
    return await authenticatedFetch<Conversation>(`${FORUM_BASE}/conversations/${conversationId}/`);
  } catch (err) {
    if (err instanceof ForumApiError && err.status === 404) return null;
    throw err;
  }
}

/**
 * Send to any conversation the viewer belongs to by its id — the only send
 * path for a group (todo 350). Throws ForumApiError 403 when the viewer is
 * not a participant or the group is block-paired with them, 400 for an
 * empty/spam body, 404 for a conversation they cannot see.
 */
export async function sendConversationMessage(
  conversationId: number,
  body: string
): Promise<DirectMessage> {
  return authenticatedFetch<DirectMessage>(
    `${FORUM_BASE}/conversations/${conversationId}/messages/`,
    { method: 'POST', body: JSON.stringify({ body }) }
  );
}

export interface CreateGroupConversationInput {
  title: string;
  /** The OTHER members (2–7); the viewer is added by the server. */
  usernames: string[];
  /** The first message — a group only exists once one was sent. */
  body: string;
}

/**
 * Create a group and send its first message in one request; resolves to the
 * new inbox row. Throws ForumApiError 400 with the server's generic "One of
 * the members cannot be added." (no oracle on which), 429 with `retryAfter`
 * from the dm_group_create bucket (5/h).
 */
export async function createGroupConversation(
  input: CreateGroupConversationInput
): Promise<Conversation> {
  return authenticatedFetch<Conversation>(`${FORUM_BASE}/conversations/`, {
    method: 'POST',
    body: JSON.stringify({ title: input.title, usernames: input.usernames, body: input.body }),
  });
}

/** Creator only (403 otherwise). Resolves to the updated row; an existing member is a no-op. */
export async function addParticipant(
  conversationId: number,
  username: string
): Promise<Conversation> {
  return authenticatedFetch<Conversation>(
    `${FORUM_BASE}/conversations/${conversationId}/participants/`,
    { method: 'POST', body: JSON.stringify({ username }) }
  );
}

/**
 * Remove a member (creator) or leave (any member removing themselves) — 204.
 * The creator cannot leave while others remain (400 from the server).
 */
export async function removeParticipant(conversationId: number, username: string): Promise<void> {
  await authenticatedFetch<void>(
    `${FORUM_BASE}/conversations/${conversationId}/participants/${encodeURIComponent(username)}/`,
    { method: 'DELETE' }
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
