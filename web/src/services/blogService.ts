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
  FetchBlogPostsOptions,
  FetchPopularPostsOptions,
} from '../types/blog';

export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/**
 * Resolve a media path against the API origin.
 *
 * When media is served locally (Django's default, and dev), it lives on the
 * API host, not the SPA host — a relative `/media/...` src breaks whenever
 * the two are on different origins (prod, and locally without a dev-server
 * proxy). The API also emits ABSOLUTE `/media/` URLs whose host isn't
 * trustworthy: `related_posts[].featured_image` is built from Wagtail's
 * static Site record (`get_full_url`), which is uncurated and resolves to
 * the wrong host in every environment where it hasn't been hand-configured
 * (live-probed: `http://localhost/media/...` — port 80, not the API's
 * actual port). Rendition payloads separately carry a `full_url` field with
 * the same Site-record problem, which is why it's deliberately not modeled
 * on `BlogPostImage` either. So: re-base ANY `/media/` PATH — relative or
 * absolute — onto `API_URL`, ignoring whatever host the API sent.
 *
 * When the backend's USE_R2 flag is on (todo 305), media instead lives on
 * an R2/CDN custom domain, and those URLs never contain a `/media/` path
 * segment (django-storages's S3Storage.url() builds
 * `https://<custom_domain>/<key>` — `/media/` only ever comes from Django's
 * local-storage MEDIA_URL). Such a URL falls through to the pass-through
 * branch below unchanged, by design, not by accident of matching only the
 * path: a host like `cdn.example.com/social-media/cover.webp` — where
 * `/media/` merely appears inside an unrelated segment — also isn't
 * mistaken for Django's media path and rebased.
 */
export function mediaUrl(url: string): string {
  if (url.startsWith('/media/')) {
    return `${API_URL}${url}`;
  }
  try {
    const parsed = new URL(url);
    if (parsed.pathname.startsWith('/media/')) {
      return `${API_URL}${parsed.pathname}${parsed.search}${parsed.hash}`;
    }
  } catch {
    // Not a valid absolute URL — fall through to the relative-path case.
  }
  return url.startsWith('/') ? `${API_URL}${url}` : url;
}

/**
 * Fetch blog posts with optional filters and pagination.
 */
export async function fetchBlogPosts(
  options: FetchBlogPostsOptions = {}
): Promise<BlogPostListResponse> {
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
export async function fetchPopularPosts(
  options: FetchPopularPostsOptions = {}
): Promise<BlogPost[]> {
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
