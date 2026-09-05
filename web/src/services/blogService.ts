/**
 * Blog API Service
 *
 * Provides methods to interact with the Wagtail blog API.
 * All endpoints are at /api/v2/ using Wagtail's API v2.
 *
 * Uses httpClient for automatic X-Request-ID header injection
 * and structured logging for distributed tracing.
 */

import axios from 'axios';
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
 * proxy). The API also emits ABSOLUTE `/media/` URLs, historically built
 * from Wagtail's static Site record (`get_full_url`), which was uncurated
 * and resolved to the wrong host in every environment where it hadn't been
 * hand-configured (live-probed 2026-08-16: `http://localhost/media/...` —
 * port 80, not the API's actual port). As of todo 308, the backend instead
 * derives every URL from the request that's actually serving it
 * (`request.build_absolute_uri()`), so the host it sends should now always
 * match `API_URL` when hit through the same domain — this rebase is kept
 * as defense-in-depth rather than removed, since it's a no-op once the
 * hosts already match. So: re-base ANY `/media/` PATH — relative or
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
 * Fetch a single blog post by slug — two requests, by necessity.
 *
 * The v2 LIST route (`/api/v2/blog-posts/?slug=…`) serves
 * `BlogPostPageListSerializer` since todo 306 routed `listing_view` to the
 * light serializer, and that serializer ignores `fields=*`: the payload has
 * no `content_blocks`, `introduction`, `related_posts` or `allow_comments`
 * (live-probed 2026-09-05, locally and in prod — the article body was
 * silently empty on this page). Only the DETAIL route
 * (`/api/v2/blog-posts/<id>/`) goes through `BlogPostPageSerializer`, and
 * Wagtail's detail route is id-addressed, so: resolve the slug to an id via
 * the listing (one row, light), then fetch the detail. Both responses are
 * server-cached (BlogCacheService), so the extra hop is cheap.
 */
export async function fetchBlogPost(slug: string): Promise<BlogPost> {
  try {
    const params = new URLSearchParams({
      type: 'blog.BlogPostPage',
      slug: slug,
      limit: '1',
    });

    const listing = await apiClient.get(`/api/v2/blog-posts/?${params}`);
    const hit = listing.data.items?.[0];

    if (!hit) {
      throw new Error('Blog post not found');
    }

    let detail;
    try {
      detail = await apiClient.get(
        `/api/v2/blog-posts/${encodeURIComponent(String(hit.id))}/?fields=*`
      );
    } catch (detailError) {
      // A listing hit that 404s on the detail hop (a stale cached listing
      // pointing at a since-unpublished page) is still "not found" — by
      // STATUS, so the page's NotFoundPage branch fires, not the generic
      // error banner.
      if (axios.isAxiosError(detailError) && detailError.response?.status === 404) {
        throw new Error('Blog post not found', { cause: detailError });
      }
      throw detailError;
    }

    return detail.data;
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
