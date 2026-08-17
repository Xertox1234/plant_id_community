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
  StreamFieldBlock,
} from '../types/blog';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/**
 * Resolve a media path against the API origin.
 *
 * Media always lives on the API host, not the SPA host — a relative
 * `/media/...` src breaks whenever the two are on different origins (prod,
 * and locally without a dev-server proxy). The API also emits ABSOLUTE
 * `/media/` URLs whose host isn't trustworthy: `related_posts[].featured_image`
 * is built from Wagtail's static Site record (`get_full_url`), which is
 * uncurated and resolves to the wrong host in every environment where it
 * hasn't been hand-configured (live-probed: `http://localhost/media/...` —
 * port 80, not the API's actual port). Rendition payloads separately carry
 * a `full_url` field with the same Site-record problem, which is why it's
 * deliberately not modeled on `BlogPostImage` either. So: re-base ANY
 * `/media/` PATH — relative or absolute — onto `API_URL`, ignoring
 * whatever host the API sent. A non-`/media/` absolute URL (e.g. a CDN
 * asset) passes through unchanged. Matched against the path only (not a
 * substring anywhere in the URL), so a host like
 * `cdn.example.com/social-media/cover.webp` — where `/media/` merely
 * appears inside an unrelated segment — isn't mistaken for Django's media
 * path and rebased.
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
 * Normalize a post's `content_blocks` field.
 *
 * DRF's `ModelSerializer` has no native mapping for Wagtail's StreamField,
 * so it falls back to a plain `ModelField` and stringifies the value.
 * Live-probed 2026-08-16: both the detail lookup below AND the
 * `fetchBlogPosts` list endpoint send `content_blocks` as a JSON string
 * (`'[{"type":"paragraph","value":"<p>…"}]'`), not an array (see the task
 * report for the backend root cause — out of scope here, the API is
 * contractually frozen). An un-parsed string crashes `StreamFieldRenderer`'s
 * `blocks.map`, so this is a frontend-only workaround: parse the string
 * back into an array so `BlogPost.content_blocks: StreamFieldBlock[]` holds
 * for every caller. An already-array value passes through unchanged; any
 * other shape (missing key, malformed JSON) degrades to `[]` rather than
 * throwing, so a bad payload renders a bodyless article instead of an
 * error boundary.
 */
function normalizeContentBlocks(blocks: unknown): StreamFieldBlock[] {
  if (Array.isArray(blocks)) {
    return blocks as StreamFieldBlock[];
  }
  if (typeof blocks !== 'string') {
    return [];
  }
  try {
    const parsed = JSON.parse(blocks);
    return Array.isArray(parsed) ? parsed : [];
  } catch (error) {
    logger.error('Failed to parse content_blocks JSON string', {
      component: 'BlogService',
      error,
    });
    return [];
  }
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
    const items: BlogPost[] = (response.data.items || []).map((item: BlogPost) => ({
      ...item,
      content_blocks: normalizeContentBlocks(item.content_blocks),
    }));

    return {
      items,
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

    const post = response.data.items[0];
    return { ...post, content_blocks: normalizeContentBlocks(post.content_blocks) };
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
