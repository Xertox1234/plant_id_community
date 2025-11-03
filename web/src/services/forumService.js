const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const FORUM_BASE = `${API_URL}/api/v1/forum`;

// Helper to get CSRF token from cookies
function getCsrfToken() {
  return document.cookie
    .split('; ')
    .find(row => row.startsWith('csrftoken='))
    ?.split('=')[1];
}

// Helper for authenticated requests
async function authenticatedFetch(url, options = {}) {
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
 * @returns {Promise<Array>} Array of category objects
 */
export async function fetchCategories() {
  return authenticatedFetch(`${FORUM_BASE}/categories/`);
}

/**
 * Fetch category tree (hierarchical structure)
 * @returns {Promise<Array>} Array of categories with children
 */
export async function fetchCategoryTree() {
  return authenticatedFetch(`${FORUM_BASE}/categories/tree/`);
}

/**
 * Fetch single category by slug
 * @param {string} slug - Category slug
 * @returns {Promise<Object>} Category object
 */
export async function fetchCategory(slug) {
  return authenticatedFetch(`${FORUM_BASE}/categories/${slug}/`);
}

/**
 * Fetch threads with filters and pagination
 * @param {Object} options
 * @param {number} options.page - Page number (1-indexed)
 * @param {number} options.limit - Items per page
 * @param {string} options.category - Category slug filter
 * @param {string} options.search - Search query
 * @param {string} options.ordering - Sort order (-last_activity_at, -created_at, etc.)
 * @returns {Promise<Object>} { items: [], meta: { count, next, previous } }
 */
export async function fetchThreads({
  page = 1,
  limit = 20,
  category = '',
  search = '',
  ordering = '-last_activity_at'
} = {}) {
  const params = new URLSearchParams({
    page: page.toString(),
    limit: limit.toString(),
    ordering,
  });

  if (category) params.append('category', category);
  if (search) params.append('search', search);

  const data = await authenticatedFetch(`${FORUM_BASE}/threads/?${params}`);

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
 * @param {string} slug - Thread slug
 * @returns {Promise<Object>} Thread object with first_post
 */
export async function fetchThread(slug) {
  return authenticatedFetch(`${FORUM_BASE}/threads/${slug}/`);
}

/**
 * Create new thread (requires authentication)
 * @param {Object} data
 * @param {string} data.title - Thread title
 * @param {string} data.category - Category UUID
 * @param {string} data.excerpt - Short excerpt
 * @param {string} data.first_post_content - First post content
 * @param {string} data.first_post_format - Content format (plain/markdown/rich)
 * @returns {Promise<Object>} Created thread object
 */
export async function createThread({
  title,
  category,
  excerpt,
  first_post_content,
  first_post_format = 'plain'
}) {
  return authenticatedFetch(`${FORUM_BASE}/threads/`, {
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
 * @param {Object} options
 * @param {string} options.thread - Thread slug (required)
 * @param {number} options.page - Page number
 * @param {number} options.limit - Items per page
 * @param {string} options.ordering - Sort order (created_at, -created_at)
 * @returns {Promise<Object>} { items: [], meta: { count, next, previous } }
 */
export async function fetchPosts({
  thread,
  page = 1,
  limit = 20,
  ordering = 'created_at'
}) {
  if (!thread) {
    throw new Error('Thread slug is required');
  }

  const params = new URLSearchParams({
    thread,
    page: page.toString(),
    limit: limit.toString(),
    ordering,
  });

  const data = await authenticatedFetch(`${FORUM_BASE}/posts/?${params}`);

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
 * @param {Object} data
 * @param {string} data.thread - Thread UUID
 * @param {string} data.content_raw - Post content
 * @param {string} data.content_format - Content format (plain/markdown/rich)
 * @returns {Promise<Object>} Created post object
 */
export async function createPost({ thread, content_raw, content_format = 'plain' }) {
  return authenticatedFetch(`${FORUM_BASE}/posts/`, {
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
 * @param {string} postId - Post UUID
 * @param {Object} data
 * @param {string} data.content_raw - Updated content
 * @param {string} data.content_format - Content format
 * @returns {Promise<Object>} Updated post object
 */
export async function updatePost(postId, { content_raw, content_format }) {
  return authenticatedFetch(`${FORUM_BASE}/posts/${postId}/`, {
    method: 'PATCH',
    body: JSON.stringify({
      content_raw,
      content_format,
    }),
  });
}

/**
 * Soft delete post (requires author or moderator)
 * @param {string} postId - Post UUID
 * @returns {Promise<void>}
 */
export async function deletePost(postId) {
  return authenticatedFetch(`${FORUM_BASE}/posts/${postId}/`, {
    method: 'DELETE',
  });
}

/**
 * Add reaction to post (requires authentication)
 * @param {Object} data
 * @param {string} data.post - Post UUID
 * @param {string} data.reaction_type - like/love/helpful/thanks
 * @returns {Promise<Object>} Created reaction object
 */
export async function addReaction({ post, reaction_type }) {
  return authenticatedFetch(`${FORUM_BASE}/reactions/`, {
    method: 'POST',
    body: JSON.stringify({
      post,
      reaction_type,
    }),
  });
}

/**
 * Remove reaction (requires authentication)
 * @param {string} reactionId - Reaction UUID
 * @returns {Promise<void>}
 */
export async function removeReaction(reactionId) {
  return authenticatedFetch(`${FORUM_BASE}/reactions/${reactionId}/`, {
    method: 'DELETE',
  });
}

/**
 * Fetch reactions for a post
 * @param {string} postId - Post UUID
 * @returns {Promise<Array>} Array of reaction objects
 */
export async function fetchReactions(postId) {
  return authenticatedFetch(`${FORUM_BASE}/reactions/?post=${postId}`);
}

/**
 * Search forum threads and posts
 * @param {Object} options
 * @param {string} options.q - Search query (required)
 * @param {string} options.category - Filter by category slug
 * @param {string} options.author - Filter by author username
 * @param {string} options.date_from - Filter by date (ISO format)
 * @param {string} options.date_to - Filter by date (ISO format)
 * @param {number} options.page - Page number (default: 1)
 * @param {number} options.page_size - Results per page (default: 20, max: 50)
 * @returns {Promise<Object>} Search results with threads and posts
 */
export async function searchForum({
  q,
  category = '',
  author = '',
  date_from = '',
  date_to = '',
  page = 1,
  page_size = 20
} = {}) {
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

  return authenticatedFetch(`${FORUM_BASE}/threads/search/?${params}`);
}

/**
 * Upload image to a post (requires authentication)
 * @param {string} postId - Post UUID
 * @param {File} imageFile - Image file to upload
 * @returns {Promise<Object>} Created attachment object with ImageKit URLs
 */
export async function uploadPostImage(postId, imageFile) {
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
 * @param {string} postId - Post UUID
 * @param {string} attachmentId - Attachment UUID
 * @returns {Promise<void>}
 */
export async function deletePostImage(postId, attachmentId) {
  return authenticatedFetch(`${FORUM_BASE}/posts/${postId}/delete_image/${attachmentId}/`, {
    method: 'DELETE',
  });
}
