/**
 * Forum API Service — translation layer.
 *
 * The backend serves an id-based, machina-shaped API; this module calls those
 * real endpoints and maps responses to the clean React domain types.
 * Lookups use integer ids (parsed from hybrid id+slug route params).
 *
 * Cookie-based JWT auth with CSRF on mutating requests.
 */
import { getCsrfToken } from '../utils/csrf';
import {
  mapForumToCategory,
  mapTopicToThread,
  mapPostToPost,
  mapImageToAttachment,
  type BackendForum,
  type BackendTopic,
  type BackendPost,
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
// Categories
// ---------------------------------------------------------------------------

export async function fetchCategories(): Promise<Category[]> {
  const data = await authenticatedFetch<DrfPage<BackendForum>>(`${FORUM_BASE}/categories/`);
  return (data.results || []).map(mapForumToCategory);
}

/** No backend tree endpoint — returns the flat list (no children). */
export async function fetchCategoryTree(): Promise<Category[]> {
  return fetchCategories();
}

/** Resolve a single category by its integer id (from the hybrid route param). */
export async function fetchCategory(forumId: number): Promise<Category> {
  const categories = await fetchCategories();
  const match = categories.find((c) => c.id === String(forumId));
  if (!match) throw new Error('Category not found');
  return match;
}

// ---------------------------------------------------------------------------
// Threads (topics)
// ---------------------------------------------------------------------------

export async function fetchThreads(
  options: { page?: number; category?: number } = {}
): Promise<PaginatedResponse<Thread>> {
  const { page = 1, category } = options;
  const params = new URLSearchParams({ page: String(page) });
  const path =
    category != null
      ? `${FORUM_BASE}/categories/${category}/topics/?${params}`
      : `${FORUM_BASE}/topics/?${params}`;
  const data = await authenticatedFetch<DrfPage<BackendTopic>>(path);
  return {
    items: (data.results || []).map(mapTopicToThread),
    meta: { count: data.count || 0, next: data.next, previous: data.previous },
  };
}

export async function fetchThread(topicId: number): Promise<Thread> {
  const data = await authenticatedFetch<{ topic: BackendTopic }>(
    `${FORUM_BASE}/topics/${topicId}/`
  );
  return mapTopicToThread(data.topic);
}

export async function createThread(data: {
  title: string;
  category: number;
  first_post_content: string;
  first_post_format?: string;
}): Promise<Thread> {
  const { title, category, first_post_content, first_post_format = 'plain' } = data;
  const res = await authenticatedFetch<{ topic: BackendTopic }>(
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
  return mapTopicToThread(res.topic);
}

// ---------------------------------------------------------------------------
// Posts
// ---------------------------------------------------------------------------

export async function fetchPosts(options: {
  thread: number;
  page?: number;
}): Promise<PaginatedResponse<Post>> {
  const { thread, page = 1 } = options;
  if (thread == null) throw new Error('Thread id is required');
  const params = new URLSearchParams({ topic: String(thread), page: String(page) });
  const data = await authenticatedFetch<DrfPage<BackendPost>>(`${FORUM_BASE}/posts/?${params}`);
  return {
    items: (data.results || []).map((p) => mapPostToPost(p, String(thread))),
    meta: { count: data.count || 0, next: data.next, previous: data.previous },
  };
}

export async function createPost(data: {
  thread: number;
  content_raw: string;
  content_format?: string;
}): Promise<Post> {
  const { thread, content_raw, content_format = 'plain' } = data;
  const res = await authenticatedFetch<{ data: BackendPost }>(`${FORUM_BASE}/posts/create/`, {
    method: 'POST',
    body: JSON.stringify({ topic: thread, content: content_raw, content_format }),
  });
  return mapPostToPost(res.data, String(thread));
}

export async function updatePost(postId: string, data: UpdatePostInput): Promise<Post> {
  const { content_raw, content_format } = data;
  const res = await authenticatedFetch<{ data: BackendPost }>(`${FORUM_BASE}/posts/${postId}/`, {
    method: 'PATCH',
    body: JSON.stringify({ content: content_raw, content_format }),
  });
  return mapPostToPost(res.data, '');
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
  const { q } = options;
  if (!q || q.trim() === '') throw new Error('Search query is required');
  const params = new URLSearchParams({ q: q.trim() });
  const data = await authenticatedFetch<{ topics: BackendTopic[]; posts: BackendPost[] }>(
    `${FORUM_BASE}/search/?${params}`
  );
  const threads = (data.topics || []).map(mapTopicToThread);
  const posts = (data.posts || []).map((p) => mapPostToPost(p, ''));
  return {
    query: q.trim(),
    threads,
    posts,
    total_threads: threads.length,
    total_posts: posts.length,
    has_next_threads: false,
    has_next_posts: false,
    page: 1,
    page_size: threads.length + posts.length,
  } as SearchForumResponse;
}
