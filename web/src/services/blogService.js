/**
 * Blog API Service
 *
 * Provides methods to interact with the Wagtail blog API.
 * All endpoints are at /api/v2/ using Wagtail's API v2.
 */

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/**
 * Fetch blog posts with optional filters and pagination.
 *
 * @param {Object} options - Query options
 * @param {number} options.page - Page number (default: 1)
 * @param {number} options.limit - Posts per page (default: 10)
 * @param {string} options.search - Search query
 * @param {string} options.category - Category slug
 * @param {string} options.tag - Tag name
 * @param {string} options.author - Author username
 * @param {string} options.order - Sort order (latest, popular, oldest)
 * @returns {Promise<Object>} - { items, meta: { total_count } }
 */
export async function fetchBlogPosts(options = {}) {
  const {
    page = 1,
    limit = 10,
    search = '',
    category = '',
    tag = '',
    author = '',
    order = 'latest',
  } = options;

  // Build query parameters
  const params = new URLSearchParams({
    limit: limit.toString(),
    offset: ((page - 1) * limit).toString(),
  });

  // Add search
  if (search) {
    params.append('search', search);
  }

  // Add filters
  if (category) {
    params.append('category_slug', category);
  }
  if (tag) {
    params.append('tag', tag);
  }
  if (author) {
    params.append('author_username', author);
  }

  // Add ordering
  if (order === 'popular') {
    params.append('order', '-view_count');
  } else if (order === 'oldest') {
    params.append('order', 'first_published_at');
  } else {
    // Default: latest
    params.append('order', '-first_published_at');
  }

  try {
    const response = await fetch(`${API_URL}/api/v2/blog-posts/?${params}`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch blog posts: ${response.status}`);
    }

    const data = await response.json();

    return {
      items: data.items || [],
      meta: data.meta || { total_count: 0 },
    };
  } catch (error) {
    console.error('[BlogService] Error fetching blog posts:', error);
    throw error;
  }
}

/**
 * Fetch a single blog post by slug.
 *
 * @param {string} slug - Post slug
 * @returns {Promise<Object>} - Blog post data
 */
export async function fetchBlogPost(slug) {
  try {
    const params = new URLSearchParams({
      type: 'blog.BlogPostPage',
      slug: slug,
      fields: '*', // Get all fields for detail view
    });

    const response = await fetch(`${API_URL}/api/v2/blog-posts/?${params}`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch blog post: ${response.status}`);
    }

    const data = await response.json();

    if (!data.items || data.items.length === 0) {
      throw new Error('Blog post not found');
    }

    return data.items[0];
  } catch (error) {
    console.error('[BlogService] Error fetching blog post:', error);
    throw error;
  }
}

/**
 * Fetch popular blog posts.
 *
 * @param {Object} options - Query options
 * @param {number} options.limit - Number of posts (default: 5)
 * @param {number} options.days - Time period in days (default: 30, 0 = all time)
 * @returns {Promise<Array>} - Array of popular blog posts
 */
export async function fetchPopularPosts(options = {}) {
  const { limit = 5, days = 30 } = options;

  try {
    const params = new URLSearchParams({
      limit: limit.toString(),
      days: days.toString(),
    });

    const response = await fetch(`${API_URL}/api/v2/blog-posts/popular/?${params}`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch popular posts: ${response.status}`);
    }

    const data = await response.json();
    return data || [];
  } catch (error) {
    console.error('[BlogService] Error fetching popular posts:', error);
    throw error;
  }
}

/**
 * Fetch blog categories.
 *
 * @returns {Promise<Array>} - Array of categories
 */
export async function fetchCategories() {
  try {
    const response = await fetch(`${API_URL}/api/v2/categories/`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch categories: ${response.status}`);
    }

    const data = await response.json();
    return data.items || [];
  } catch (error) {
    console.error('[BlogService] Error fetching categories:', error);
    return []; // Return empty array on error (non-critical)
  }
}

/**
 * NOTE: Related posts are included in the blog post detail response.
 * This function is kept for backwards compatibility but is no longer needed.
 * The related_posts field is already populated in fetchBlogPost().
 *
 * @param {string} postId - Post ID
 * @returns {Promise<Array>} - Array of related posts (always empty - use post.related_posts instead)
 */
export async function fetchRelatedPosts(postId) {
  // Related posts are now included in the blog post detail API response
  // No need for a separate endpoint call
  return [];
}
