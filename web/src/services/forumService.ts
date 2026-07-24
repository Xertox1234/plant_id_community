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

// ---------------------------------------------------------------------------
// Categories (boards)
// ---------------------------------------------------------------------------

export async function fetchCategories(): Promise<Category[]> {
  // BoardListView returns {results: [...]} (pagination_class = None, but still
  // wraps in {results} via its custom list() override — verified in views.py:111).
  const data = await authenticatedFetch<{ results: BackendBoard[] }>(`${FORUM_BASE}/boards/`);
  return (data.results || []).map(mapBoardToCategory);
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
    // Legacy caller fields — accepted but ignored.
    category?: number;
    page?: number;
    search?: string;
    ordering?: string;
  } = {}
): Promise<PaginatedResponse<Thread>> {
  const { board, cursor, sort } = options;
  if (!board) throw new Error('A board slug is required');
  // A cursor URL is absolute and already encodes the active sort ordering, so
  // ?sort= only ever needs to be appended on a first-page (non-cursor) request.
  let url = cursor || `${FORUM_BASE}/boards/${board}/topics/`;
  if (!cursor && sort) url += `?sort=${encodeURIComponent(sort)}`;
  const data = await authenticatedFetch<DrfPage<BackendTopicListItem>>(url);
  return {
    items: (data.results || []).map(mapTopicListItemToThread),
    meta: { count: 0, next: data.next, previous: data.previous },
  };
}

export async function fetchThread(topicId: number): Promise<Thread> {
  const data = await authenticatedFetch<BackendTopicDetail>(`${FORUM_BASE}/topics/${topicId}/`);
  return mapTopicDetailToThread(data);
}

export async function createThread(data: CreateTopicInput): Promise<CreateTopicResult> {
  const { boardSlug, title, content } = data;
  const res = await authenticatedFetch<{
    id: number;
    slug: string;
    status: 'published' | 'pending';
  }>(`${FORUM_BASE}/boards/${boardSlug}/topics/`, {
    method: 'POST',
    body: JSON.stringify({ title, slug: slugifyTitle(title), body: htmlToBodyBlocks(content) }),
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

export interface ForumUserSearchResult {
  username: string;
  display_name: string;
}

/** Search usernames by prefix, for the @mention composer autocomplete (todo 253 slice 4). */
export async function searchForumUsers(query: string): Promise<ForumUserSearchResult[]> {
  return authenticatedFetch<ForumUserSearchResult[]>(
    `${FORUM_BASE}/users/search/?q=${encodeURIComponent(query)}`
  );
}

/** Fetch a user's public forum profile + recent activity (todo 257 H7). */
export async function fetchUserProfile(username: string): Promise<ForumUserProfile> {
  return authenticatedFetch<ForumUserProfile>(
    `${FORUM_BASE}/users/${encodeURIComponent(username)}/`
  );
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
    meta: { count: 0, next: data.next, previous: data.previous },
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
export async function uploadPostImage(imageFile: File): Promise<UploadedImage> {
  const csrfToken = await getCsrfToken();
  const formData = new FormData();
  formData.append('image', imageFile);
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
  const { q, category, page } = options;
  if (!q || q.trim() === '') throw new Error('Search query is required');
  const params = new URLSearchParams({ q: q.trim() });
  if (category) params.set('board', category);
  if (page && page > 1) params.set('page', String(page));
  const data = await authenticatedFetch<{
    topics: BackendSearchTopic[];
    posts: BackendSearchPost[];
    topics_has_more?: boolean;
    posts_has_more?: boolean;
  }>(`${FORUM_BASE}/search/?${params}`);
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
