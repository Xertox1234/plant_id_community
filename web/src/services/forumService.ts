/**
 * Forum API Service — translation layer.
 *
 * READ functions target the wagtail_forum API contract (Tasks 1-4).
 * WRITE functions (createThread, createPost, updatePost, deletePost,
 * toggleReaction, image fns) are Phase 2/3 — left structurally intact
 * so they still compile, but their endpoints will 404 until Phase 2 lands.
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
  mapImageToAttachment,
  type BackendBoard,
  type BackendTopicListItem,
  type BackendTopicDetail,
  type BackendPost,
  type BackendSearchTopic,
  type BackendSearchPost,
  type BackendImage,
} from './forumMappers';
import type {
  Category,
  Thread,
  Post,
  Attachment,
  PaginatedResponse,
  UpdatePostInput,
  SearchForumOptions,
  SearchForumResponse,
  ReactionToggleResult,
} from '../types/forum';

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
    // Legacy caller fields — accepted but ignored until Task 6 updates callers.
    category?: number;
    page?: number;
    search?: string;
    ordering?: string;
  } = {}
): Promise<PaginatedResponse<Thread>> {
  const { board, cursor } = options;
  if (!board) throw new Error('A board slug is required');
  const url = cursor || `${FORUM_BASE}/boards/${board}/topics/`;
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

export async function createThread(data: {
  title: string;
  category: number;
  first_post_content: string;
  first_post_format?: string;
}): Promise<Thread> {
  // Phase 2 will migrate this to POST /boards/{slug}/topics/ with a body[] payload.
  // Left structurally intact so it compiles; endpoint will 404 until Phase 2.
  const { title, category, first_post_content, first_post_format = 'plain' } = data;
  const res = await authenticatedFetch<{ topic: BackendTopicDetail }>(
    `${FORUM_BASE}/categories/${category}/topics/create/`,
    {
      method: 'POST',
      body: JSON.stringify({
        subject: title,
        content: first_post_content,
        content_format: first_post_format,
      }),
    }
  );
  return mapTopicDetailToThread(res.topic);
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

export async function createPost(data: {
  thread: number;
  content_raw: string;
  content_format?: string;
}): Promise<Post> {
  // Phase 2 will migrate to POST /topics/{id}/replies/ with a body[] payload.
  const { thread, content_raw, content_format = 'plain' } = data;
  const res = await authenticatedFetch<{ data: BackendPost }>(`${FORUM_BASE}/posts/create/`, {
    method: 'POST',
    body: JSON.stringify({ topic: thread, content: content_raw, content_format }),
  });
  if (!res?.data) {
    throw new Error('createPost: response is missing "data" — unexpected response shape');
  }
  return mapPostToPost(res.data, String(thread));
}

export async function updatePost(postId: string, data: UpdatePostInput): Promise<Post> {
  const { content_raw, content_format } = data;
  const res = await authenticatedFetch<{ data: BackendPost }>(`${FORUM_BASE}/posts/${postId}/`, {
    method: 'PATCH',
    body: JSON.stringify({ content: content_raw, content_format }),
  });
  return mapPostToPost(res.data, String(res.data.topic_id));
}

export async function deletePost(postId: string): Promise<void> {
  await authenticatedFetch<void>(`${FORUM_BASE}/posts/${postId}/delete/`, { method: 'DELETE' });
}

// ---------------------------------------------------------------------------
// Reactions (toggle model)
// ---------------------------------------------------------------------------

interface BackendReactionResponse {
  reactions?: Record<string, { count: number; users: unknown[] }>;
  user_reactions?: string[];
  action?: 'added' | 'removed';
  reaction_type?: string;
}

function toCounts(r: BackendReactionResponse): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const [type, info] of Object.entries(r.reactions || {})) counts[type] = info.count;
  return counts;
}

/** Toggle a reaction on a post; returns updated counts + the user's active reactions. */
export async function toggleReaction(
  postId: string,
  reactionType: string
): Promise<ReactionToggleResult> {
  const res = await authenticatedFetch<BackendReactionResponse>(
    `${FORUM_BASE}/posts/${postId}/reactions/`,
    { method: 'POST', body: JSON.stringify({ reaction_type: reactionType }) }
  );
  return {
    action: res.action || 'added',
    reaction_type: res.reaction_type || reactionType,
    reaction_counts: toCounts(res),
    user_reactions: res.user_reactions || [],
  };
}

/** Read reaction counts + the current user's active reactions for a post. */
export async function fetchReactions(
  postId: string
): Promise<{ reaction_counts: Record<string, number>; user_reactions: string[] }> {
  const res = await authenticatedFetch<BackendReactionResponse>(
    `${FORUM_BASE}/posts/${postId}/reactions/`
  );
  return { reaction_counts: toCounts(res), user_reactions: res.user_reactions || [] };
}

// ---------------------------------------------------------------------------
// Images
// ---------------------------------------------------------------------------

export async function fetchPostImages(postId: string): Promise<Attachment[]> {
  const data = await authenticatedFetch<{ images: BackendImage[] }>(
    `${FORUM_BASE}/posts/${postId}/images/`
  );
  return (data.images || []).map(mapImageToAttachment);
}

export async function uploadPostImage(postId: string, imageFile: File): Promise<Attachment> {
  const csrfToken = await getCsrfToken();
  const formData = new FormData();
  formData.append('images', imageFile); // backend expects the plural field name
  const response = await fetch(`${FORUM_BASE}/posts/${postId}/images/upload/`, {
    method: 'POST',
    credentials: 'include',
    headers: { Accept: 'application/json', ...(csrfToken && { 'X-CSRFToken': csrfToken }) },
    body: formData,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Upload failed' }));
    throw new Error(error.message || error.detail || `HTTP ${response.status}`);
  }
  const data = (await response.json()) as { images: BackendImage[] };
  if (!data.images?.length) throw new Error('Upload returned no image');
  return mapImageToAttachment(data.images[0]);
}

export async function deletePostImage(postId: string, attachmentId: string): Promise<void> {
  await authenticatedFetch<void>(`${FORUM_BASE}/posts/${postId}/images/${attachmentId}/delete/`, {
    method: 'DELETE',
  });
}

/** No bulk reorder endpoint — PATCH upload_order on each image in sequence. */
export async function reorderPostImages(
  postId: string,
  attachmentIds: string[]
): Promise<Attachment[]> {
  for (let i = 0; i < attachmentIds.length; i++) {
    await authenticatedFetch<unknown>(`${FORUM_BASE}/posts/${postId}/images/${attachmentIds[i]}/`, {
      method: 'PATCH',
      body: JSON.stringify({ upload_order: i }),
    });
  }
  return fetchPostImages(postId);
}

// ---------------------------------------------------------------------------
// Search
// ---------------------------------------------------------------------------

export async function searchForum(options: SearchForumOptions): Promise<SearchForumResponse> {
  // Note: SearchForumOptions includes category/author/date_from/date_to/page/page_size
  // for backward compat with SearchPage; the backend only supports `q` currently.
  const { q } = options;
  if (!q || q.trim() === '') throw new Error('Search query is required');
  const params = new URLSearchParams({ q: q.trim() });
  const data = await authenticatedFetch<{
    topics: BackendSearchTopic[];
    posts: BackendSearchPost[];
  }>(`${FORUM_BASE}/search/?${params}`);
  const threads = (data.topics || []).map(mapSearchTopicToThread);
  const posts = (data.posts || []).map(mapSearchPostToPost);
  return {
    query: q.trim(),
    threads,
    posts,
    total_threads: threads.length,
    total_posts: posts.length,
    has_next_threads: false,
    has_next_posts: false,
    page: options.page ?? 1,
    page_size: options.page_size ?? threads.length + posts.length,
  };
}
