/**
 * Blog comment API service (todo 352) — the DRF v1 `/api/v1/blog/` comment
 * endpoints, which `blogService.ts` (Wagtail API v2, read-only) never
 * touched.
 *
 * Its own module in the same shape as `messageService.ts`: cookie-based JWT
 * auth with CSRF on mutating requests, and failures throw `ForumApiError`
 * so callers branch on the HTTP status — 429 rate-limited, 403 comments
 * disabled, 400 field error — instead of sniffing message text.
 */
import { getCsrfToken } from '../utils/csrf';
import { ForumApiError } from './forumService';
import type { BlogComment } from '../types/blog';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const BLOG_BASE = `${API_URL}/api/v1/blog`;

/**
 * Client-side cap on one comment body. The backend `content` is an
 * uncapped TextField, so this is a UI choice, not a contract: 2000 keeps a
 * comment to a few paragraphs (the forum DM cap is 4000) and gives the
 * composer a counter to show. Raise it here and the composer follows.
 */
export const BLOG_COMMENT_MAX_LENGTH = 2000;

export interface AddBlogCommentInput {
  content: string;
  /** Id of the APPROVED, TOP-LEVEL comment being replied to (depth is one). */
  parent?: number | null;
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
    // Two body shapes: the host exception envelope `{message}` (a DRF
    // exception — field errors arrive flattened as "field: text", 429 as
    // "Rate limit exceeded…") and a plain `{detail}` Response (comments
    // disabled, self-flag).
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
 * Top-level comments (each with its one level of `replies`) for a post:
 * approved ones plus the caller's OWN pending ones. Public — an anonymous
 * caller gets the approved set. Throws `ForumApiError` 403 when the post
 * has comments disabled.
 */
export async function fetchBlogComments(postId: number): Promise<BlogComment[]> {
  return authenticatedFetch<BlogComment[]>(
    `${BLOG_BASE}/posts/${encodeURIComponent(String(postId))}/comments/`
  );
}

/**
 * Post a comment, or a reply when `parent` is given. The returned comment's
 * `is_approved` says whether it is live or held for moderation (spam screen
 * or a low forum trust level) — a held one is visible to its author only.
 */
export async function addBlogComment(
  postId: number,
  input: AddBlogCommentInput
): Promise<BlogComment> {
  const body: { content: string; parent?: number } = { content: input.content };
  if (input.parent != null) body.parent = input.parent;
  return authenticatedFetch<BlogComment>(
    `${BLOG_BASE}/posts/${encodeURIComponent(String(postId))}/add_comment/`,
    { method: 'POST', body: JSON.stringify(body) }
  );
}

/**
 * Flag a comment for moderation. Repeat flags by the same user are
 * accepted but counted once; flagging your own comment is a 400.
 */
export async function flagBlogComment(commentId: number): Promise<{ detail: string }> {
  return authenticatedFetch<{ detail: string }>(
    `${BLOG_BASE}/comments/${encodeURIComponent(String(commentId))}/flag/`,
    { method: 'POST' }
  );
}
