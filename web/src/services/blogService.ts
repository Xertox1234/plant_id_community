/**
 * Blog API Service
 *
 * Provides methods to interact with the Wagtail blog API.
 * All endpoints are at /api/v2/ using Wagtail's API v2.
 *
 * Uses httpClient for automatic X-Request-ID header injection
 * and structured logging for distributed tracing.
 */

import apiClient from '../utils/httpClient';
import { logger } from '../utils/logger';
import type {
  BlogPost,
  BlogPostListResponse,
  BlogCategory,
  BlogCategoryListResponse,
  FetchBlogPostsOptions,
  FetchPopularPostsOptions,
} from '../types/blog';

/**
 * Fetch blog posts with optional filters and pagination.
 */
export async function fetchBlogPosts(options: FetchBlogPostsOptions = {}): Promise<BlogPostListResponse> {
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
    const response = await apiClient.get(`/api/v2/blog-posts/?${params}`);

    return {
      items: response.data.items || [],
      meta: response.data.meta || { total_count: 0 },
    };
  } catch (error) {
    logger.error('Error fetching blog posts', {
      component: 'BlogService',
      error,
      context: { params: options },
    });
    throw error;
  }
}

/**
 * Fetch a single blog post by slug.
 */
export async function fetchBlogPost(slug: string): Promise<BlogPost> {
  try {
    const params = new URLSearchParams({
      type: 'blog.BlogPostPage',
      slug: slug,
      fields: '*', // Get all fields for detail view
    });

    const response = await apiClient.get(`/api/v2/blog-posts/?${params}`);

    if (!response.data.items || response.data.items.length === 0) {
      throw new Error('Blog post not found');
    }

    return response.data.items[0];
  } catch (error) {
    logger.error('Error fetching blog post', {
      component: 'BlogService',
      error,
      context: { slug },
    });
    throw error;
  }
}

/**
 * Fetch popular blog posts.
 */
export async function fetchPopularPosts(options: FetchPopularPostsOptions = {}): Promise<BlogPost[]> {
  const { limit = 5, days = 30 } = options;

  try {
    const params = new URLSearchParams({
      limit: limit.toString(),
      days: days.toString(),
    });

    const response = await apiClient.get(`/api/v2/blog-posts/popular/?${params}`);
    return response.data || [];
  } catch (error) {
    logger.error('Error fetching popular posts', {
      component: 'BlogService',
      error,
      context: { limit, days },
    });
    throw error;
  }
}

/**
 * Fetch blog categories.
 */
export async function fetchCategories(): Promise<BlogCategory[]> {
  try {
    const response = await apiClient.get('/api/v2/categories/');
    return response.data.items || [];
  } catch (error) {
    logger.error('Error fetching categories', {
      component: 'BlogService',
      error,
    });
    return []; // Return empty array on error (non-critical)
  }
}

/**
 * NOTE: Related posts are included in the blog post detail response.
 * This function is kept for backwards compatibility but is no longer needed.
 * The related_posts field is already populated in fetchBlogPost().
 *
 * @returns Array of related posts (always empty - use post.related_posts instead)
 */
export async function fetchRelatedPosts(): Promise<BlogPost[]> {
  // Related posts are now included in the blog post detail API response
  // No need for a separate endpoint call
  return [];
}
