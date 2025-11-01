/**
 * Blog API Service
 *
 * Provides methods to interact with the Wagtail blog API.
 * All endpoints are at /api/v2/ using Wagtail's API v2.
 *
 * Uses httpClient for automatic X-Request-ID header injection
 * and structured logging for distributed tracing.
 */

import apiClient from '../utils/httpClient'
import { logger } from '../utils/logger'

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
    const response = await apiClient.get(`/api/v2/blog-posts/?${params}`)

    return {
      items: response.data.items || [],
      meta: response.data.meta || { total_count: 0 },
    }
  } catch (error) {
    logger.error('Error fetching blog posts', {
      component: 'BlogService',
      error,
      context: { params: options },
    })
    throw error
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
    })

    const response = await apiClient.get(`/api/v2/blog-posts/?${params}`)

    if (!response.data.items || response.data.items.length === 0) {
      throw new Error('Blog post not found')
    }

    return response.data.items[0]
  } catch (error) {
    logger.error('Error fetching blog post', {
      component: 'BlogService',
      error,
      context: { slug },
    })
    throw error
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
    })

    const response = await apiClient.get(`/api/v2/blog-posts/popular/?${params}`)
    return response.data || []
  } catch (error) {
    logger.error('Error fetching popular posts', {
      component: 'BlogService',
      error,
      context: { limit, days },
    })
    throw error
  }
}

/**
 * Fetch blog categories.
 *
 * @returns {Promise<Array>} - Array of categories
 */
export async function fetchCategories() {
  try {
    const response = await apiClient.get('/api/v2/categories/')
    return response.data.items || []
  } catch (error) {
    logger.error('Error fetching categories', {
      component: 'BlogService',
      error,
    })
    return [] // Return empty array on error (non-critical)
  }
}

/**
 * NOTE: Related posts are included in the blog post detail response.
 * This function is kept for backwards compatibility but is no longer needed.
 * The related_posts field is already populated in fetchBlogPost().
 *
 * @returns {Promise<Array>} - Array of related posts (always empty - use post.related_posts instead)
 */
export async function fetchRelatedPosts() {
  // Related posts are now included in the blog post detail API response
  // No need for a separate endpoint call
  return [];
}
