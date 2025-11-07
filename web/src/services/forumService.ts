/**
 * Forum API Service
 *
 * Provides methods to interact with the forum API.
 * All endpoints are at /api/v1/forum/ using DRF viewsets.
 *
 * Uses cookie-based JWT authentication with CSRF protection.
 */

import type {
  Category,
  Thread,
  Post,
  Attachment,
  Reaction,
  PaginatedResponse,
  FetchThreadsOptions,
  FetchPostsOptions,
  CreateThreadInput,
  CreatePostInput,
  UpdatePostInput,
  AddReactionInput,
  SearchForumOptions,
} from '../types/forum';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const FORUM_BASE = `${API_URL}/api/v1/forum`;

/**
 * Helper to get CSRF token from cookies
 */
function getCsrfToken(): string | undefined {
  return document.cookie
    .split('; ')
    .find(row => row.startsWith('csrftoken='))
    ?.split('=')[1];
}

/**
 * Helper for authenticated requests with generic return type
 */
async function authenticatedFetch<T>(url: string, options: RequestInit = {}): Promise<T> {
  const csrfToken = getCsrfToken();

  const response = await fetch(url, {
    ...options,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      ...(csrfToken && { 'X-CSRFToken': csrfToken }),
      ...options.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Fetch all categories
 */
export async function fetchCategories(): Promise<Category[]> {
  return authenticatedFetch<Category[]>(`${FORUM_BASE}/categories/`);
}

/**
 * Fetch category tree (hierarchical structure)
 */
export async function fetchCategoryTree(): Promise<Category[]> {
  return authenticatedFetch<Category[]>(`${FORUM_BASE}/categories/tree/`);
}

/**
 * Fetch single category by slug
 */
export async function fetchCategory(slug: string): Promise<Category> {
  return authenticatedFetch<Category>(`${FORUM_BASE}/categories/${slug}/`);
}

/**
 * Fetch threads with filters and pagination
 */
export async function fetchThreads(options: FetchThreadsOptions = {}): Promise<PaginatedResponse<Thread>> {
  const {
    page = 1,
    limit = 20,
    category = '',
    search = '',
    ordering = '-last_activity_at'
  } = options;

  const params = new URLSearchParams({
    page: page.toString(),
    limit: limit.toString(),
    ordering,
  });

  if (category) params.append('category', category);
  if (search) params.append('search', search);

  const data = await authenticatedFetch<{
    results?: Thread[];
    count?: number;
    next?: string | null;
    previous?: string | null;
  }>(`${FORUM_BASE}/threads/?${params}`);

  return {
    items: data.results || [],
    meta: {
      count: data.count || 0,
      next: data.next,
      previous: data.previous,
    },
  };
}

/**
 * Fetch single thread by slug
 */
export async function fetchThread(slug: string): Promise<Thread> {
  return authenticatedFetch<Thread>(`${FORUM_BASE}/threads/${slug}/`);
}

/**
 * Create new thread (requires authentication)
 */
export async function createThread(data: CreateThreadInput): Promise<Thread> {
  const {
    title,
    category,
    excerpt,
    first_post_content,
    first_post_format = 'plain'
  } = data;

  return authenticatedFetch<Thread>(`${FORUM_BASE}/threads/`, {
    method: 'POST',
    body: JSON.stringify({
      title,
      category,
      excerpt,
      first_post_content,
      first_post_format,
    }),
  });
}

/**
 * Fetch posts in a thread
 */
export async function fetchPosts(options: FetchPostsOptions): Promise<PaginatedResponse<Post>> {
  const {
    thread,
    page = 1,
    limit = 20,
    ordering = 'created_at'
  } = options;

  if (!thread) {
    throw new Error('Thread slug is required');
  }

  const params = new URLSearchParams({
    thread,
    page: page.toString(),
    limit: limit.toString(),
    ordering,
  });

  const data = await authenticatedFetch<{
    results?: Post[];
    count?: number;
    next?: string | null;
    previous?: string | null;
  }>(`${FORUM_BASE}/posts/?${params}`);

  return {
    items: data.results || [],
    meta: {
      count: data.count || 0,
      next: data.next,
      previous: data.previous,
    },
  };
}

/**
 * Create new post in a thread (requires authentication)
 */
export async function createPost(data: CreatePostInput): Promise<Post> {
  const { thread, content_raw, content_format = 'plain' } = data;

  return authenticatedFetch<Post>(`${FORUM_BASE}/posts/`, {
    method: 'POST',
    body: JSON.stringify({
      thread,
      content_raw,
      content_format,
    }),
  });
}

/**
 * Update existing post (requires author or moderator)
 */
export async function updatePost(postId: string, data: UpdatePostInput): Promise<Post> {
  const { content_raw, content_format } = data;

  return authenticatedFetch<Post>(`${FORUM_BASE}/posts/${postId}/`, {
    method: 'PATCH',
    body: JSON.stringify({
      content_raw,
      content_format,
    }),
  });
}

/**
 * Soft delete post (requires author or moderator)
 */
export async function deletePost(postId: string): Promise<void> {
  return authenticatedFetch<void>(`${FORUM_BASE}/posts/${postId}/`, {
    method: 'DELETE',
  });
}

/**
 * Add reaction to post (requires authentication)
 */
export async function addReaction(data: AddReactionInput): Promise<Reaction> {
  const { post, reaction_type } = data;

  return authenticatedFetch<Reaction>(`${FORUM_BASE}/reactions/`, {
    method: 'POST',
    body: JSON.stringify({
      post,
      reaction_type,
    }),
  });
}

/**
 * Remove reaction (requires authentication)
 */
export async function removeReaction(reactionId: string): Promise<void> {
  return authenticatedFetch<void>(`${FORUM_BASE}/reactions/${reactionId}/`, {
    method: 'DELETE',
  });
}

/**
 * Fetch reactions for a post
 */
export async function fetchReactions(postId: string): Promise<Reaction[]> {
  return authenticatedFetch<Reaction[]>(`${FORUM_BASE}/reactions/?post=${postId}`);
}

/**
 * Search forum threads and posts
 */
export async function searchForum(options: SearchForumOptions): Promise<{
  threads: Thread[];
  posts: Post[];
  meta: {
    count: number;
    next?: string | null;
    previous?: string | null;
  };
}> {
  const {
    q,
    category = '',
    author = '',
    date_from = '',
    date_to = '',
    page = 1,
    page_size = 20
  } = options;

  if (!q || q.trim() === '') {
    throw new Error('Search query is required');
  }

  const params = new URLSearchParams({
    q: q.trim(),
    page: page.toString(),
    page_size: page_size.toString(),
  });

  if (category) params.append('category', category);
  if (author) params.append('author', author);
  if (date_from) params.append('date_from', date_from);
  if (date_to) params.append('date_to', date_to);

  return authenticatedFetch<{
    threads: Thread[];
    posts: Post[];
    meta: {
      count: number;
      next?: string | null;
      previous?: string | null;
    };
  }>(`${FORUM_BASE}/threads/search/?${params}`);
}

/**
 * Upload image to a post (requires authentication)
 */
export async function uploadPostImage(postId: string, imageFile: File): Promise<Attachment> {
  const csrfToken = getCsrfToken();
  const formData = new FormData();
  formData.append('image', imageFile);

  const response = await fetch(`${FORUM_BASE}/posts/${postId}/upload_image/`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Accept': 'application/json',
      ...(csrfToken && { 'X-CSRFToken': csrfToken }),
    },
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Upload failed' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Delete image from a post (requires authentication)
 */
export async function deletePostImage(postId: string, attachmentId: string): Promise<void> {
  return authenticatedFetch<void>(`${FORUM_BASE}/posts/${postId}/delete_image/${attachmentId}/`, {
    method: 'DELETE',
  });
}
