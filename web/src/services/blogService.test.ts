/**
 * Blog Service Tests
 *
 * Comprehensive tests for blog service covering:
 * - Blog post fetching with filters and pagination
 * - Single post fetching by slug
 * - Popular posts fetching
 * - Category fetching
 * - Error handling
 *
 * Priority: P1 - CRITICAL (Public-facing blog feature)
 * Coverage Target: 100% branch coverage
 * Estimated Test Count: 15 tests
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  fetchBlogPosts,
  fetchBlogPost,
  fetchPopularPosts,
  fetchCategories,
  fetchRelatedPosts,
} from './blogService';
import type {
  BlogPost,
  BlogPostListResponse,
  BlogCategory,
  FetchBlogPostsOptions,
} from '../types/blog';
import apiClient from '../utils/httpClient';

// Mock logger to prevent console noise
vi.mock('../utils/logger', () => ({
  logger: {
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    debug: vi.fn(),
  },
}));

// Mock apiClient
vi.mock('../utils/httpClient', () => ({
  default: {
    get: vi.fn(),
  },
}));

describe('blogService', () => {
  // Test fixtures
  const mockBlogPost: BlogPost = {
    id: 1,
    meta: {
      type: 'blog.BlogPostPage',
      detail_url: '/api/v2/pages/1/',
      html_url: '/blog/test-post/',
      slug: 'test-post',
      first_published_at: '2025-01-01T00:00:00Z',
    },
    slug: 'test-post',
    title: 'Test Blog Post',
    introduction: 'This is a test post introduction',
    content_blocks: [
      { type: 'heading', value: 'Test Heading', id: '1' },
      { type: 'paragraph', value: 'Test paragraph content', id: '2' },
    ],
    featured_image: {
      url: 'https://example.com/image.jpg',
      thumbnail: {
        url: 'https://example.com/image-thumb.jpg',
      },
    },
    publish_date: '2025-01-01',
    author: {
      first_name: 'John',
      last_name: 'Doe',
    },
    tags: ['plants', 'care'],
    categories: [{ name: 'Plant Care' }],
    view_count: 100,
  };

  const mockBlogPostListResponse: BlogPostListResponse = {
    items: [mockBlogPost],
    meta: {
      total_count: 1,
    },
  };

  const mockCategory: BlogCategory = {
    id: 1,
    name: 'Plant Care',
    slug: 'plant-care',
    description: 'Tips for taking care of plants',
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ============================================================================
  // FETCH BLOG POSTS TESTS
  // ============================================================================

  describe('fetchBlogPosts', () => {
    it('should fetch blog posts with default options', async () => {
      // Arrange
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: mockBlogPostListResponse,
      });

      // Act
      const result = await fetchBlogPosts();

      // Assert
      expect(result).toEqual(mockBlogPostListResponse);
      expect(apiClient.get).toHaveBeenCalledWith(
        expect.stringContaining('/api/v2/blog-posts/')
      );
      const callUrl = vi.mocked(apiClient.get).mock.calls[0][0];
      expect(callUrl).toContain('limit=10');
      expect(callUrl).toContain('offset=0');
      expect(callUrl).toContain('order=-first_published_at');
    });

    it('should fetch blog posts with pagination', async () => {
      // Arrange
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: mockBlogPostListResponse,
      });

      // Act
      await fetchBlogPosts({ page: 3, limit: 20 });

      // Assert
      const callUrl = vi.mocked(apiClient.get).mock.calls[0][0];
      expect(callUrl).toContain('limit=20');
      expect(callUrl).toContain('offset=40'); // (3-1) * 20 = 40
    });

    it('should fetch blog posts with search filter', async () => {
      // Arrange
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: mockBlogPostListResponse,
      });

      // Act
      await fetchBlogPosts({ search: 'watering tips' });

      // Assert
      const callUrl = vi.mocked(apiClient.get).mock.calls[0][0];
      expect(callUrl).toContain('search=watering+tips');
    });

    it('should fetch blog posts with category, tag, and author filters', async () => {
      // Arrange
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: mockBlogPostListResponse,
      });

      // Act
      await fetchBlogPosts({
        category: 'plant-care',
        tag: 'beginner',
        author: 'johndoe',
      });

      // Assert
      const callUrl = vi.mocked(apiClient.get).mock.calls[0][0];
      expect(callUrl).toContain('category_slug=plant-care');
      expect(callUrl).toContain('tag=beginner');
      expect(callUrl).toContain('author_username=johndoe');
    });

    it('should fetch blog posts ordered by popularity', async () => {
      // Arrange
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: mockBlogPostListResponse,
      });

      // Act
      await fetchBlogPosts({ order: 'popular' });

      // Assert
      const callUrl = vi.mocked(apiClient.get).mock.calls[0][0];
      expect(callUrl).toContain('order=-view_count');
    });

    it('should fetch blog posts ordered by oldest', async () => {
      // Arrange
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: mockBlogPostListResponse,
      });

      // Act
      await fetchBlogPosts({ order: 'oldest' });

      // Assert
      const callUrl = vi.mocked(apiClient.get).mock.calls[0][0];
      expect(callUrl).toContain('order=first_published_at');
    });

    it('should handle empty response gracefully', async () => {
      // Arrange
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: {},
      });

      // Act
      const result = await fetchBlogPosts();

      // Assert
      expect(result).toEqual({
        items: [],
        meta: { total_count: 0 },
      });
    });

    it('should handle API errors', async () => {
      // Arrange
      const error = new Error('API error');
      vi.mocked(apiClient.get).mockRejectedValueOnce(error);

      // Act & Assert
      await expect(fetchBlogPosts()).rejects.toThrow('API error');
    });
  });

  // ============================================================================
  // FETCH BLOG POST (SINGLE) TESTS
  // ============================================================================

  describe('fetchBlogPost', () => {
    it('should fetch a single blog post by slug', async () => {
      // Arrange
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: {
          items: [mockBlogPost],
          meta: { total_count: 1 },
        },
      });

      // Act
      const result = await fetchBlogPost('test-post');

      // Assert
      expect(result).toEqual(mockBlogPost);
      const callUrl = vi.mocked(apiClient.get).mock.calls[0][0];
      expect(callUrl).toContain('slug=test-post');
      expect(callUrl).toContain('type=blog.BlogPostPage');
      expect(callUrl).toContain('fields=*');
    });

    it('should throw error when blog post is not found', async () => {
      // Arrange
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: {
          items: [],
          meta: { total_count: 0 },
        },
      });

      // Act & Assert
      await expect(fetchBlogPost('non-existent')).rejects.toThrow(
        'Blog post not found'
      );
    });

    it('should handle API errors', async () => {
      // Arrange
      const error = new Error('Network error');
      vi.mocked(apiClient.get).mockRejectedValueOnce(error);

      // Act & Assert
      await expect(fetchBlogPost('test-post')).rejects.toThrow('Network error');
    });
  });

  // ============================================================================
  // FETCH POPULAR POSTS TESTS
  // ============================================================================

  describe('fetchPopularPosts', () => {
    it('should fetch popular posts with default options', async () => {
      // Arrange
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: [mockBlogPost],
      });

      // Act
      const result = await fetchPopularPosts();

      // Assert
      expect(result).toEqual([mockBlogPost]);
      const callUrl = vi.mocked(apiClient.get).mock.calls[0][0];
      expect(callUrl).toContain('/blog-posts/popular/');
      expect(callUrl).toContain('limit=5');
      expect(callUrl).toContain('days=30');
    });

    it('should fetch popular posts with custom options', async () => {
      // Arrange
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: [mockBlogPost],
      });

      // Act
      await fetchPopularPosts({ limit: 10, days: 7 });

      // Assert
      const callUrl = vi.mocked(apiClient.get).mock.calls[0][0];
      expect(callUrl).toContain('limit=10');
      expect(callUrl).toContain('days=7');
    });

    it('should handle API errors', async () => {
      // Arrange
      const error = new Error('API error');
      vi.mocked(apiClient.get).mockRejectedValueOnce(error);

      // Act & Assert
      await expect(fetchPopularPosts()).rejects.toThrow('API error');
    });
  });

  // ============================================================================
  // FETCH CATEGORIES TESTS
  // ============================================================================

  describe('fetchCategories', () => {
    it('should fetch all blog categories', async () => {
      // Arrange
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: {
          items: [mockCategory],
        },
      });

      // Act
      const result = await fetchCategories();

      // Assert
      expect(result).toEqual([mockCategory]);
      expect(apiClient.get).toHaveBeenCalledWith('/api/v2/categories/');
    });

    it('should return empty array on API error (non-critical)', async () => {
      // Arrange
      const error = new Error('API error');
      vi.mocked(apiClient.get).mockRejectedValueOnce(error);

      // Act
      const result = await fetchCategories();

      // Assert
      expect(result).toEqual([]);
    });

    it('should handle empty categories response', async () => {
      // Arrange
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: {},
      });

      // Act
      const result = await fetchCategories();

      // Assert
      expect(result).toEqual([]);
    });
  });

  // ============================================================================
  // FETCH RELATED POSTS TESTS (DEPRECATED)
  // ============================================================================

  describe('fetchRelatedPosts', () => {
    it('should always return empty array (deprecated)', async () => {
      // Act
      const result = await fetchRelatedPosts();

      // Assert
      expect(result).toEqual([]);
      expect(apiClient.get).not.toHaveBeenCalled();
    });
  });
});
