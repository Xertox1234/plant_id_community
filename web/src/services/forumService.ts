/**
 * Forum API Service — translation layer for the wagtail_forum REST API.
 *
 * READ and WRITE functions (create topic/reply, edit, delete, react) target the
 * wagtail_forum contract. The image functions remain on the legacy shape pending
 * PR-3 (inline-image upload + render); they are not wired into any compose UI.
 *
 * Cookie-based JWT auth with CSRF on mutating requests.
 */
import { getCsrfToken } from '../utils/csrf';
import {
  mapBoardToCategory,
  mapTopicListItemToThread,
  mapTopicDetailToThread,
  mapPostToPost,
  mapSearchTopicToThread,
  mapSearchPostToPost,
  type BackendBoard,
  type BackendTopicListItem,
  type BackendTopicDetail,
  type BackendPost,
  type BackendSearchTopic,
  type BackendSearchPost,
} from './forumMappers';
import type {
  Category,
  ForumAuthor,
  ForumIndexPayload,
  Thread,
  Post,
  PaginatedResponse,
  CreateTopicInput,
  CreateTopicResult,
  CreateReplyInput,
  CreateReplyResult,
  UpdatePostInput,
  EditPostResult,
  SearchForumOptions,
  SearchForumResponse,
  ReactionToggleResult,
  ForumUserProfile,
  ForumMyStats,
  RecentTopic,
  ForumExpert,
  EventHero,
  BlockedUser,
  MutedUser,
  ForumMyProfile,
  ForumMyProfilePatch,
  ThreadPoll,
  PlantCareAnswer,
} from '../types/forum';
import { slugifyTitle } from '../utils/forumUrls';
import { htmlToBodyBlocks } from '../utils/forumBody';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const FORUM_BASE = `${API_URL}/api/v1/forum`;

interface DrfPage<T> {
  results?: T[];
  count?: number;
  next?: string | null;
  previous?: string | null;
}

/**
 * A failed forum request, carrying the HTTP status.
 *
 * Extends Error with the same `message`, so every existing caller and
 * `instanceof Error` check is unaffected — but a caller for whom the KIND of
 * failure is product behaviour can branch on `status` instead of sniffing the
 * message text. Sniffing does not work: the backend serialises DRF's
 * `PermissionDenied` as its default detail ("You do not have permission to
 * perform this action."), which contains neither the code nor the word
 * "forbidden" (`apps/core/exceptions.py` builds `message` as `str(exc)` for a
 * single-detail error; field-level validation errors are flattened instead).
 */
export class ForumApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ForumApiError';
    this.status = status;
  }
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
      response.status
    );
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}

// ---------------------------------------------------------------------------
// Categories (boards)
// ---------------------------------------------------------------------------

/**
 * Fetch the forum home payload: boards + the CMS welcome copy.
 *
 * BoardListView returns `{results, intro}` — flat, no cursor. `intro` rides
 * this envelope rather than taking its own endpoint because it renders on the
 * same screen (todo 278 L2; the package README's `## List envelopes` table is
 * the contract).
 */
export async function fetchForumIndex(): Promise<ForumIndexPayload> {
  const data = await authenticatedFetch<{ results: BackendBoard[]; intro?: string }>(
    `${FORUM_BASE}/boards/`
  );
  return {
    categories: (data.results || []).map(mapBoardToCategory),
    intro: data.intro || '',
  };
}

export async function fetchCategories(): Promise<Category[]> {
  return (await fetchForumIndex()).categories;
}

/** No backend tree endpoint — returns the flat list (no children). */
export const fetchCategoryTree = fetchCategories;

/**
 * Resolve a single category by its integer id.
 * Fetches the boards list and scans for the matching id string.
 * (Slug-based lookup is Task 6 — callers still pass a numeric id from parseLeadingId.)
 */
export async function fetchCategory(forumId: number): Promise<Category> {
  const categories = await fetchCategories();
  const match = categories.find((c) => c.id === String(forumId));
  if (!match) throw new Error('Category not found');
  return match;
}

// ---------------------------------------------------------------------------
// Threads (topics)
// ---------------------------------------------------------------------------

/**
 * Fetch topics for a board.
 *
 * New signature: { board: string; cursor?: string }
 * Legacy fields (category, page, search, ordering) are accepted for backward
 * compat with existing callers (ThreadListPage) so global type-check passes;
 * they are ignored until Task 6 updates the callers.
 *
 * CURSOR NOTE: DRF cursor `next`/`previous` are absolute URLs.
 * `authenticatedFetch` passes its `url` argument straight to `fetch()` with no
 * base prepended, so absolute cursor URLs are safe to pass through unchanged.
 */
export async function fetchThreads(
  options: {
    board?: string;
    cursor?: string;
    /** Board-list sort — one of the TopicCursorPagination SORT_ORDERINGS keys. */
    sort?: string;
    /** Secondary-taxonomy filter (audit M5) — a single normalized tag name. */
    tag?: string;
    // Legacy caller fields — accepted but ignored.
    category?: number;
    page?: number;
    search?: string;
    ordering?: string;
  } = {}
): Promise<PaginatedResponse<Thread>> {
  const { board, cursor, sort, tag } = options;
  if (!board) throw new Error('A board slug is required');
  // A cursor URL is absolute and already encodes the active sort ordering AND
  // tag filter, so query params are only appended on a first-page request.
  let url = cursor || `${FORUM_BASE}/boards/${board}/topics/`;
  if (!cursor) {
    const params = new URLSearchParams();
    if (sort) params.set('sort', sort);
    if (tag) params.set('tag', tag);
    const qs = params.toString();
    if (qs) url += `?${qs}`;
  }
  const data = await authenticatedFetch<DrfPage<BackendTopicListItem>>(url);
  return {
    items: (data.results || []).map(mapTopicListItemToThread),
    // Cursor pagination omits a total, so `count` is undefined here; pages that
    // want a real total seed it from board.topic_count / thread.post_count (M30).
    meta: { count: data.count ?? 0, next: data.next, previous: data.previous },
  };
}

export async function fetchThread(
  topicId: number,
  options: {
    // A poll for new replies: the backend skips the view-count increment and
    // the topic-read record, so an open tab neither inflates views nor marks
    // replies the reader has not loaded as seen (todo 346).
    peek?: boolean;
  } = {}
): Promise<Thread> {
  const query = options.peek ? '?peek=1' : '';
  const data = await authenticatedFetch<BackendTopicDetail>(
    `${FORUM_BASE}/topics/${topicId}/${query}`
  );
  return mapTopicDetailToThread(data);
}

export async function createThread(data: CreateTopicInput): Promise<CreateTopicResult> {
  const { boardSlug, title, content, tags, identification, poll } = data;
  const res = await authenticatedFetch<{
    id: number;
    slug: string;
    status: 'published' | 'pending';
  }>(`${FORUM_BASE}/boards/${boardSlug}/topics/`, {
    method: 'POST',
    body: JSON.stringify({
      title,
      slug: slugifyTitle(title),
      body: htmlToBodyBlocks(content),
      // Omit the key entirely when there are none — the server treats an absent
      // `tags` as "no tags", and sending [] would be an equivalent but noisier
      // payload on the common untagged path.
      ...(tags?.length ? { tags } : {}),
      // Same omit-when-absent rule as tags: the common compose has no
      // attachment, and the server treats an absent key as "none".
      ...(identification ? { identification } : {}),
      // Same omit-when-absent rule again: most threads carry no poll.
      ...(poll ? { poll } : {}),
    }),
  });
  return { id: String(res.id), slug: res.slug, status: res.status };
}

/** Follow a topic — the user is notified of future replies. Idempotent. */
export async function subscribeToTopic(topicId: number): Promise<void> {
  await authenticatedFetch<{ subscribed: boolean }>(
    `${FORUM_BASE}/topics/${topicId}/subscription/`,
    {
      method: 'POST',
    }
  );
}

/** Unfollow a topic. Idempotent. */
export async function unsubscribeFromTopic(topicId: number): Promise<void> {
  await authenticatedFetch<{ subscribed: boolean }>(
    `${FORUM_BASE}/topics/${topicId}/subscription/`,
    {
      method: 'DELETE',
    }
  );
}

/** Save a topic for later — distinct from subscribeToTopic's notify-me intent
 * (todo 283 / M2). Idempotent. */
export async function bookmarkTopic(topicId: number): Promise<void> {
  await authenticatedFetch<{ bookmarked: boolean }>(`${FORUM_BASE}/topics/${topicId}/bookmark/`, {
    method: 'POST',
  });
}

/** Remove a saved topic. Idempotent. */
export async function unbookmarkTopic(topicId: number): Promise<void> {
  await authenticatedFetch<{ bookmarked: boolean }>(`${FORUM_BASE}/topics/${topicId}/bookmark/`, {
    method: 'DELETE',
  });
}

/**
 * Cast this user's ballot in a thread's poll (audit M8; N-of-K since todo 349).
 *
 * `optionIds` is 1..`max_choices` option ids. Returns the poll with freshly
 * aggregated results — the server is the only thing that counts votes, so the
 * caller replaces its poll state with this rather than incrementing anything
 * locally.
 *
 * One submission per user per poll. A second submission is REJECTED with 409,
 * not replaced; callers should branch on `err.status === 409` rather than on
 * the message text (the backend's wording is not a contract).
 */
export async function votePoll(topicId: number, optionIds: number[]): Promise<ThreadPoll> {
  return authenticatedFetch<ThreadPoll>(`${FORUM_BASE}/topics/${topicId}/poll/vote/`, {
    method: 'POST',
    body: JSON.stringify({ option_ids: optionIds }),
  });
}

/** The accepted-answer state a mark/clear returns (audit H6). */
export interface SolutionResult {
  is_solved: boolean;
  solved_post_id: number | null;
  solved_at: string | null;
}

/**
 * Accept a post as the topic's answer. Only the topic's author or a moderator
 * may call this; anyone else gets a 403 from the backend.
 */
export async function markSolution(topicId: number, postId: number): Promise<SolutionResult> {
  return authenticatedFetch<SolutionResult>(`${FORUM_BASE}/topics/${topicId}/solution/`, {
    method: 'POST',
    body: JSON.stringify({ post_id: postId }),
  });
}

/** Clear the topic's accepted answer. Idempotent — clearing an unsolved topic is a no-op. */
export async function clearSolution(topicId: number): Promise<SolutionResult> {
  return authenticatedFetch<SolutionResult>(`${FORUM_BASE}/topics/${topicId}/solution/`, {
    method: 'DELETE',
  });
}

export interface ForumUserSearchResult {
  username: string;
  display_name: string;
}

/** Search usernames by prefix, for the @mention composer autocomplete (todo 253 slice 4). */
export async function searchForumUsers(
  query: string,
  signal?: AbortSignal
): Promise<ForumUserSearchResult[]> {
  return authenticatedFetch<ForumUserSearchResult[]>(
    `${FORUM_BASE}/users/search/?q=${encodeURIComponent(query)}`,
    { signal }
  );
}

/** Fetch a user's public forum profile + recent activity (todo 257 H7). */
export async function fetchUserProfile(username: string): Promise<ForumUserProfile> {
  return authenticatedFetch<ForumUserProfile>(
    `${FORUM_BASE}/users/${encodeURIComponent(username)}/`
  );
}

/** Block a member — hides their forum content and stops their reply/mention
 * notifications reaching you (todo 284/M9). Idempotent. */
export async function blockUser(username: string): Promise<void> {
  await authenticatedFetch<{ blocked: boolean }>(
    `${FORUM_BASE}/users/${encodeURIComponent(username)}/block/`,
    { method: 'POST' }
  );
}

/** Unblock a member. Idempotent. */
export async function unblockUser(username: string): Promise<void> {
  await authenticatedFetch<{ blocked: boolean }>(
    `${FORUM_BASE}/users/${encodeURIComponent(username)}/block/`,
    { method: 'DELETE' }
  );
}

/** Fetch the caller's blocked members, most recently blocked first. Flat,
 * unpaginated — matches the backend's low-cardinality contract (todo 284/M9). */
export async function fetchBlockedUsers(): Promise<BlockedUser[]> {
  return authenticatedFetch<BlockedUser[]>(`${FORUM_BASE}/me/blocks/`);
}

/** Mute a member (todo 347) — hides their forum content and stops their
 * reply/mention notifications reaching YOU; nothing changes for them and
 * their messages still arrive (the lighter tool beside block). Idempotent. */
export async function muteUser(username: string): Promise<void> {
  await authenticatedFetch<{ muted: boolean }>(
    `${FORUM_BASE}/users/${encodeURIComponent(username)}/mute/`,
    { method: 'POST' }
  );
}

/** Unmute a member. Idempotent. */
export async function unmuteUser(username: string): Promise<void> {
  await authenticatedFetch<{ muted: boolean }>(
    `${FORUM_BASE}/users/${encodeURIComponent(username)}/mute/`,
    { method: 'DELETE' }
  );
}

/** Fetch the caller's muted members, most recently muted first. Flat,
 * unpaginated — same low-cardinality contract as the blocklist (todo 347). */
export async function fetchMutedUsers(): Promise<MutedUser[]> {
  return authenticatedFetch<MutedUser[]>(`${FORUM_BASE}/me/mutes/`);
}

// ---------------------------------------------------------------------------
// Own profile (me/profile/)
// ---------------------------------------------------------------------------

/** Fetch the caller's own forum profile, including the weekly digest email
 * preference (todo 340) and the fully resolved per-channel notification
 * matrix (todo 343). Auth required — anonymous callers get a 401. */
export async function fetchMyForumProfile(): Promise<ForumMyProfile> {
  return authenticatedFetch<ForumMyProfile>(`${FORUM_BASE}/me/profile/`);
}

/** Partially update the caller's own forum profile — the digest cadence
 * (todo 340) and/or a PARTIAL notification matrix (todo 343; only the cells
 * sent are merged). Resolves with the full, updated profile — the same shape
 * `fetchMyForumProfile` returns. */
export async function updateMyForumProfile(patch: ForumMyProfilePatch): Promise<ForumMyProfile> {
  return authenticatedFetch<ForumMyProfile>(`${FORUM_BASE}/me/profile/`, {
    method: 'PATCH',
    body: JSON.stringify(patch),
  });
}

// ---------------------------------------------------------------------------
// Posts
// ---------------------------------------------------------------------------

/**
 * Fetch posts for a topic (cursor-paginated).
 *
 * New signature: { thread: number; cursor?: string }
 * `page` is accepted for backward compat (ThreadDetailPage); ignored until Task 6.
 *
 * CURSOR NOTE: absolute cursor URLs are passed through unchanged — see fetchThreads.
 */
export async function fetchPosts(options: {
  thread: number;
  cursor?: string;
  // Legacy caller field — accepted but ignored until Task 6.
  page?: number;
}): Promise<PaginatedResponse<Post>> {
  const { thread, cursor } = options;
  if (thread == null) throw new Error('Thread id is required');
  const url = cursor || `${FORUM_BASE}/topics/${thread}/posts/`;
  const data = await authenticatedFetch<DrfPage<BackendPost>>(url);
  return {
    items: (data.results || []).map((p) => mapPostToPost(p, String(thread))),
    // Cursor pagination omits a total, so `count` is undefined here; pages that
    // want a real total seed it from board.topic_count / thread.post_count (M30).
    meta: { count: data.count ?? 0, next: data.next, previous: data.previous },
  };
}

export async function createPost(data: CreateReplyInput): Promise<CreateReplyResult> {
  const { thread, content } = data;
  const res = await authenticatedFetch<{ id: number; status: 'published' | 'pending' }>(
    `${FORUM_BASE}/topics/${thread}/posts/`,
    { method: 'POST', body: JSON.stringify({ body: htmlToBodyBlocks(content) }) }
  );
  return { id: String(res.id), status: res.status };
}

export async function updatePost(postId: string, data: UpdatePostInput): Promise<EditPostResult> {
  const res = await authenticatedFetch<
    BackendPost & { moderation_status: 'published' | 'pending' }
  >(`${FORUM_BASE}/posts/${postId}/`, {
    method: 'PATCH',
    body: JSON.stringify({ body: htmlToBodyBlocks(data.content) }),
  });
  return { post: mapPostToPost(res, String(res.topic_id)), status: res.moderation_status };
}

// ---------------------------------------------------------------------------
// Edit history (todo 282 / audit M4)
// ---------------------------------------------------------------------------

export interface PostRevisionSummary {
  id: number;
  created_at: string;
  // Never null: `serialize_forum_author` maps a NULL revision user to the
  // `[deleted]` sentinel OBJECT, the same as every other author field (M41).
  user: ForumAuthor;
}

export interface PostRevisionDetail extends PostRevisionSummary {
  body: Post['body'];
}

/**
 * List a post's edit history, newest first.
 *
 * 403 is an expected outcome, not an error to swallow: the backend serves this
 * to the post's author and to moderators, and it becomes moderator-only once
 * anyone else has edited the post (earlier revisions still hold whatever that
 * edit removed). Callers should surface the refusal rather than showing an
 * empty history, which would read as "no edits".
 */
export async function fetchPostRevisions(postId: string): Promise<PostRevisionSummary[]> {
  return authenticatedFetch<PostRevisionSummary[]>(`${FORUM_BASE}/posts/${postId}/revisions/`);
}

/** One revision's body, in the same shape as the live post body. */
export async function fetchPostRevision(
  postId: string,
  revisionId: number
): Promise<PostRevisionDetail> {
  return authenticatedFetch<PostRevisionDetail>(
    `${FORUM_BASE}/posts/${postId}/revisions/${revisionId}/`
  );
}

export async function deletePost(postId: string): Promise<void> {
  await authenticatedFetch<void>(`${FORUM_BASE}/posts/${postId}/`, { method: 'DELETE' });
}

// ---------------------------------------------------------------------------
// Reactions (toggle model)
// ---------------------------------------------------------------------------

/** Toggle a reaction on a post; returns updated counts + this user's resulting state. */
export async function toggleReaction(
  postId: string,
  reactionType: string
): Promise<ReactionToggleResult> {
  return authenticatedFetch<ReactionToggleResult>(`${FORUM_BASE}/posts/${postId}/reactions/`, {
    method: 'POST',
    body: JSON.stringify({ type: reactionType }),
  });
}

// ---------------------------------------------------------------------------
// Reports
// ---------------------------------------------------------------------------

/**
 * Report a post for moderator review. Idempotent per (post, reporter); the
 * backend never echoes a report/flag count, so there is nothing to return
 * beyond success.
 */
export async function reportPost(postId: string, reason: string, detail?: string): Promise<void> {
  await authenticatedFetch<{ reported: boolean }>(`${FORUM_BASE}/posts/${postId}/reports/`, {
    method: 'POST',
    body: JSON.stringify({ reason, detail: detail ?? '' }),
  });
}

// ---------------------------------------------------------------------------
// Images (inline post images — Spec 2 PR-3)
// ---------------------------------------------------------------------------

export interface UploadedImage {
  id: number;
  url: string;
  alt: string;
  width: number;
  height: number;
}

/**
 * Upload an inline image into the forum image collection. Topic-independent:
 * the returned id is referenced from an `image` body block (see utils/forumBody).
 * Multipart, so let the browser set Content-Type; CSRF + cookie auth as usual.
 */
/**
 * Upload an inline post image, optionally with author-supplied alt text (M7).
 *
 * `alt` is sent only when non-empty — an omitted part and an empty one mean the
 * same thing to the backend (a decorative image, served as `alt: ""`), and not
 * sending it keeps the request identical to the pre-M7 shape.
 */
export async function uploadPostImage(imageFile: File, alt?: string): Promise<UploadedImage> {
  const csrfToken = await getCsrfToken();
  const formData = new FormData();
  formData.append('image', imageFile);
  const trimmedAlt = alt?.trim();
  if (trimmedAlt) formData.append('alt', trimmedAlt);
  const response = await fetch(`${FORUM_BASE}/images/`, {
    method: 'POST',
    credentials: 'include',
    headers: { Accept: 'application/json', ...(csrfToken && { 'X-CSRFToken': csrfToken }) },
    body: formData,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Upload failed' }));
    throw new Error(error.detail || error.message || `HTTP ${response.status}`);
  }
  return response.json() as Promise<UploadedImage>;
}

// ---------------------------------------------------------------------------
// Search
// ---------------------------------------------------------------------------

export async function searchForum(options: SearchForumOptions): Promise<SearchForumResponse> {
  const { q, category, page, signal } = options;
  if (!q || q.trim() === '') throw new Error('Search query is required');
  const params = new URLSearchParams({ q: q.trim() });
  if (category) params.set('board', category);
  if (page && page > 1) params.set('page', String(page));
  const data = await authenticatedFetch<{
    topics: BackendSearchTopic[];
    posts: BackendSearchPost[];
    topics_has_more?: boolean;
    posts_has_more?: boolean;
  }>(`${FORUM_BASE}/search/?${params}`, { signal });
  const threads = (data.topics || []).map(mapSearchTopicToThread);
  const posts = (data.posts || []).map(mapSearchPostToPost);
  // Each section is paginated (PAGE_SIZE per page); *_has_more says whether a
  // further page exists. total_* are this page's lengths — SearchPage sums the
  // accumulated results across Load More.
  return {
    query: q.trim(),
    threads,
    posts,
    total_threads: threads.length,
    total_posts: posts.length,
    has_more_threads: data.topics_has_more ?? false,
    has_more_posts: data.posts_has_more ?? false,
  };
}

// ---------------------------------------------------------------------------
// Landing page — event hero + "Your season" (Task 9)
// ---------------------------------------------------------------------------

/** Fetch the current user's all-time forum stats ("Your season" cards). Auth required. */
export async function fetchMyStats(): Promise<ForumMyStats> {
  return authenticatedFetch<ForumMyStats>(`${FORUM_BASE}/me/stats/`);
}

/** Fetch the most recently active topics for the landing rail / event hero. Public. */
export async function fetchRecentTopics(limit = 5): Promise<RecentTopic[]> {
  const data = await authenticatedFetch<{ results: RecentTopic[] }>(
    `${FORUM_BASE}/topics/recent/?limit=${limit}`
  );
  return data.results || [];
}

/** Fetch the community's expert roster. Public. */
export async function fetchExperts(): Promise<ForumExpert[]> {
  const data = await authenticatedFetch<{ results: ForumExpert[] }>(`${FORUM_BASE}/users/experts/`);
  return data.results || [];
}

/** Fetch the currently-featured landing-page event hero, or `{topic: null}`. Public. */
export async function fetchEventHero(): Promise<EventHero> {
  return authenticatedFetch<EventHero>(`${FORUM_BASE}/event/`);
}

// ---------------------------------------------------------------------------
// AI composer assist (todo 275 / M14)
// ---------------------------------------------------------------------------

/**
 * Error from the compose-assist endpoint, carrying the HTTP status and the
 * backend's machine-readable `code`.
 *
 * `authenticatedFetch` collapses every failure to a bare `Error`, which is fine
 * for endpoints whose only failure mode is "it broke". Here the failure kind IS
 * the product behaviour, and the composer permanently stops offering its button
 * for a permanent failure but not a transient one.
 *
 * **`permanent` deliberately does NOT include a bare 503.** The endpoint returns
 * 503 for three different reasons and only one is permanent: the feature flag
 * being off (`code: "disabled"`), versus a provider error, timeout, or empty
 * completion (`code: "unavailable"`). Latching on the status meant a single
 * provider blip disabled the button for the whole tab, with a tooltip blaming
 * the user's account — and the session-scoped latch below made that stick
 * (todo 275 code review).
 */
export class ComposeAssistError extends Error {
  readonly status: number;
  /** Backend discriminator: 'disabled' | 'unavailable' | undefined (non-503). */
  readonly code?: string;
  /** True only when retrying can never succeed for this user/deployment. */
  readonly permanent: boolean;

  constructor(status: number, message: string, code?: string) {
    super(message);
    this.name = 'ComposeAssistError';
    this.status = status;
    this.code = code;
    // 403 = not a premium account (permanent until the entitlement changes, which
    // clears the latch — see resetComposeAssistAvailability's callers).
    // 503 = permanent ONLY when the deployment has the feature off.
    this.permanent = status === 403 || code === 'disabled';
  }
}

/**
 * Session-scoped latch: once the server has said this account/deployment can
 * never use compose assist (403/503), remember it here rather than in component
 * state. The reply composer is remounted (`key={composerKey}`) after every post,
 * which resets component state — so a per-instance flag would re-offer, and
 * re-fail, the button on every reply. Session-lifetime API capability, so it
 * lives with the API client rather than in a component.
 *
 * Written by the caller (which already branches on `ComposeAssistError.permanent`)
 * rather than inside `improveDraft`, so there is exactly one place that decides
 * "permanent" and the flag is still set when a test stubs the request out.
 */
let composeAssistUnavailable = false;

export function isComposeAssistUnavailable(): boolean {
  return composeAssistUnavailable;
}

export function markComposeAssistUnavailable(): void {
  composeAssistUnavailable = true;
}

/**
 * Clear the latch. Called by `AuthContext` on every auth-state change, and by
 * tests (module state otherwise leaks between cases in a file).
 *
 * Production callers matter: the 403 latch means "this ACCOUNT is not premium",
 * so it must not outlive the account. Without this, a non-premium user who
 * clicks the button, then upgrades or logs out and back in as someone else in
 * the same SPA session (no page reload), keeps a permanently disabled button the
 * server would now allow (todo 275 code review).
 */
export function resetComposeAssistAvailability(): void {
  composeAssistUnavailable = false;
}

/**
 * Ask the backend to improve the current draft. Returns PLAIN TEXT — the caller
 * must insert it as a text node, never as HTML (see the endpoint's contract in
 * apps/forum_host/compose_assist.py).
 *
 * Ships inert: the endpoint 503s until FORUM_COMPOSE_ASSIST_ENABLED is set, and
 * 403s for non-premium accounts. Both are surfaced to the user verbatim rather
 * than swallowed, so nobody is left clicking a silently dead button.
 */
export async function improveDraft(draftHtml: string): Promise<string> {
  const csrfToken = await getCsrfToken();
  const response = await fetch(`${FORUM_BASE}/compose/assist/`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
      ...(csrfToken && { 'X-CSRFToken': csrfToken }),
    },
    body: JSON.stringify({ text: draftHtml }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ComposeAssistError(
      response.status,
      body.detail || body.message || `HTTP ${response.status}`,
      body.code
    );
  }
  const data = (await response.json()) as { text?: string };
  const text = (data.text || '').trim();
  if (!text) throw new ComposeAssistError(response.status, 'AI assist returned nothing.');
  return text;
}

// ---------------------------------------------------------------------------
// RAG plant-care answers (todo 289 / M13)
// ---------------------------------------------------------------------------

/**
 * Error from the plant-care ask endpoint — same contract as `ComposeAssistError`
 * (status + backend `code`, `permanent` only when retrying can never work),
 * plus 401: `/forum/search` is PUBLIC, so an anonymous visitor sees the
 * affordance and the server's 401 teaches. A bare 503 is transient
 * (`code: "unavailable"` covers a provider blip AND an exhausted retrieval
 * budget); only `code: "disabled"` means the deployment has the feature off.
 */
export class RagError extends Error {
  readonly status: number;
  /** Backend discriminator: 'disabled' | 'unavailable' | undefined (non-503). */
  readonly code?: string;
  /** True only when retrying can never succeed for this visitor/deployment. */
  readonly permanent: boolean;

  constructor(status: number, message: string, code?: string) {
    super(message);
    this.name = 'RagError';
    this.status = status;
    this.code = code;
    this.permanent = status === 401 || status === 403 || code === 'disabled';
  }
}

/**
 * Session-scoped latch, the compose-assist pattern: once the server has said
 * this visitor/deployment can never ask (401/403/disabled), remember it here
 * so a remounted panel does not re-offer and re-fail. Cleared by `AuthContext`
 * on every auth-state change — a 401/403 latch is about the ACCOUNT and must
 * not outlive it — and by tests.
 */
let plantCareAskUnavailable = false;

export function isPlantCareAskUnavailable(): boolean {
  return plantCareAskUnavailable;
}

export function markPlantCareAskUnavailable(): void {
  plantCareAskUnavailable = true;
}

export function resetPlantCareAskAvailability(): void {
  plantCareAskUnavailable = false;
}

const PLANT_CARE_STATUSES: ReadonlySet<string> = new Set([
  'answered',
  'passages_only',
  'no_information',
  'referral',
]);

/**
 * Ask a plant-care question answered ONLY from this site's blog + forum. The
 * envelope is status-discriminated (see `PlantCareAnswer`); "no information"
 * and a blocked question are results, not errors. Ships inert: the endpoint
 * 503s `code: "disabled"` until FORUM_RAG_ENABLED is set.
 */
export async function askPlantCare(question: string): Promise<PlantCareAnswer> {
  const csrfToken = await getCsrfToken();
  const response = await fetch(`${FORUM_BASE}/care/ask/`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
      ...(csrfToken && { 'X-CSRFToken': csrfToken }),
    },
    body: JSON.stringify({ question }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new RagError(
      response.status,
      body.detail || body.message || `HTTP ${response.status}`,
      body.code
    );
  }
  const data = (await response.json()) as Partial<PlantCareAnswer>;
  if (!data || typeof data.status !== 'string' || !PLANT_CARE_STATUSES.has(data.status)) {
    throw new RagError(response.status, 'Plant-care answer came back in an unknown shape.');
  }
  return data as PlantCareAnswer;
}

/** Report an answered plant-care answer as wrong (moderator review loop). */
export async function reportPlantCareAnswer(answerId: number, detail: string): Promise<void> {
  await authenticatedFetch<{ reported: boolean }>(
    `${FORUM_BASE}/care/answers/${answerId}/report/`,
    { method: 'POST', body: JSON.stringify({ detail }) }
  );
}
