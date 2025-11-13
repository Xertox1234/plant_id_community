/**
 * Forum Service Tests
 *
 * Comprehensive tests for forum service covering:
 * - Category operations (fetch all, tree, single)
 * - Thread operations (fetch, create, search, pagination)
 * - Post operations (fetch, create, update, delete)
 * - Reaction operations (add, remove, fetch)
 * - Image upload operations (upload, delete, validation)
 * - Search functionality with filters
 * - Error handling and validation
 *
 * Priority: P1 - CRITICAL (Forum is core community feature)
 * Coverage Target: 95%+ branch coverage
 * Estimated Test Count: 27 tests
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  fetchCategories,
  fetchCategoryTree,
  fetchCategory,
  fetchThreads,
  fetchThread,
  createThread,
  fetchPosts,
  createPost,
  updatePost,
  deletePost,
  addReaction,
  removeReaction,
  fetchReactions,
  searchForum,
  uploadPostImage,
  deletePostImage,
} from './forumService';
import type {
  Category,
  Thread,
  Post,
  Reaction,
  Attachment,
  CreateThreadInput,
  CreatePostInput,
  UpdatePostInput,
  AddReactionInput,
  SearchForumOptions,
} from '../types/forum';

// Test fixtures
const mockUser = {
  id: 1,
  email: 'test@example.com',
  username: 'testuser',
  display_name: 'Test User',
  trust_level: 'basic' as const,
};

const mockCategory: Category = {
  id: 'cat-123',
  name: 'Plant Care',
  slug: 'plant-care',
  description: 'Tips and advice for plant care',
  thread_count: 42,
  post_count: 156,
  created_at: '2025-01-01T00:00:00Z',
};

const mockThread: Thread = {
  id: 'thread-123',
  title: 'How to care for succulents?',
  slug: 'how-to-care-for-succulents',
  excerpt: 'Looking for succulent care tips',
  category: mockCategory,
  author: mockUser,
  created_at: '2025-01-01T00:00:00Z',
  last_activity_at: '2025-01-02T00:00:00Z',
  post_count: 5,
  view_count: 42,
  is_pinned: false,
  is_locked: false,
  is_active: true,
};

const mockPost: Post = {
  id: 'post-123',
  thread: 'thread-123',
  author: { ...mockUser, trust_level: 'basic' },
  content_raw: 'This is a test post',
  content_html: '<p>This is a test post</p>',
  content_format: 'markdown',
  created_at: '2025-01-01T00:00:00Z',
  is_first_post: false,
  is_active: true,
  reaction_counts: { like: 5, love: 2 },
};

const mockAttachment: Attachment = {
  id: 'attach-123',
  image: 'https://example.com/image.jpg',
  image_thumbnail: 'https://example.com/image_thumb.jpg',
  uploaded_at: '2025-01-01T00:00:00Z',
};

const mockReaction: Reaction = {
  id: 'reaction-123',
  post: 'post-123',
  user: mockUser,
  reaction_type: 'like',
  created_at: '2025-01-01T00:00:00Z',
};

// Mock fetch
let fetchMock: ReturnType<typeof vi.fn>;
let documentCookieMock: string;

beforeEach(() => {
  fetchMock = vi.fn();
  global.fetch = fetchMock;

  // Mock document.cookie
  documentCookieMock = 'csrftoken=test-csrf-token';
  Object.defineProperty(document, 'cookie', {
    get: () => documentCookieMock,
    set: (value: string) => {
      documentCookieMock = value;
    },
    configurable: true,
  });

  vi.clearAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('forumService', () => {
  // ============================================================================
  // CATEGORY TESTS
  // ============================================================================

  describe('fetchCategories', () => {
    it('should fetch all categories', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => [mockCategory],
      });

      // Act
      const result = await fetchCategories();

      // Assert
      expect(result).toEqual([mockCategory]);
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/forum/categories/'),
        expect.objectContaining({
          credentials: 'include',
          headers: expect.objectContaining({
            'X-CSRFToken': 'test-csrf-token',
          }),
        })
      );
    });

    it('should handle empty category list', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => [],
      });

      // Act
      const result = await fetchCategories();

      // Assert
      expect(result).toEqual([]);
    });

    it('should handle API errors gracefully', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => ({ detail: 'Server error' }),
      });

      // Act & Assert
      await expect(fetchCategories()).rejects.toThrow('Server error');
    });
  });

  describe('fetchCategoryTree', () => {
    it('should fetch hierarchical category structure', async () => {
      // Arrange
      const treeData: Category[] = [
        {
          ...mockCategory,
          children: [
            {
              id: 'cat-456',
              name: 'Watering',
              slug: 'watering',
              created_at: '2025-01-01T00:00:00Z',
            },
          ],
        },
      ];
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => treeData,
      });

      // Act
      const result = await fetchCategoryTree();

      // Assert
      expect(result).toEqual(treeData);
      expect(result[0].children).toHaveLength(1);
    });
  });

  describe('fetchCategory', () => {
    it('should fetch single category by slug', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => mockCategory,
      });

      // Act
      const result = await fetchCategory('plant-care');

      // Assert
      expect(result).toEqual(mockCategory);
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/categories/plant-care/'),
        expect.any(Object)
      );
    });

    it('should handle 404 for invalid slug', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: async () => ({ detail: 'Not found' }),
      });

      // Act & Assert
      await expect(fetchCategory('invalid-slug')).rejects.toThrow('Not found');
    });
  });

  // ============================================================================
  // THREAD TESTS
  // ============================================================================

  describe('fetchThreads', () => {
    it('should fetch threads with default pagination', async () => {
      // Arrange
      const response = {
        results: [mockThread],
        count: 1,
        next: null,
        previous: null,
      };
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => response,
      });

      // Act
      const result = await fetchThreads();

      // Assert
      expect(result.items).toEqual([mockThread]);
      expect(result.meta.count).toBe(1);
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('page=1'),
        expect.any(Object)
      );
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('limit=20'),
        expect.any(Object)
      );
    });

    it('should filter threads by category', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ results: [mockThread], count: 1 }),
      });

      // Act
      await fetchThreads({ category: 'plant-care' });

      // Assert
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('category=plant-care'),
        expect.any(Object)
      );
    });

    it('should search threads by query', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ results: [mockThread], count: 1 }),
      });

      // Act
      await fetchThreads({ search: 'succulents' });

      // Assert
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('search=succulents'),
        expect.any(Object)
      );
    });

    it('should paginate thread results', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ results: [mockThread], count: 100 }),
      });

      // Act
      await fetchThreads({ page: 2, limit: 10 });

      // Assert
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('page=2'),
        expect.any(Object)
      );
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('limit=10'),
        expect.any(Object)
      );
    });

    it('should handle custom ordering', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ results: [mockThread], count: 1 }),
      });

      // Act
      await fetchThreads({ ordering: '-created_at' });

      // Assert
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('ordering=-created_at'),
        expect.any(Object)
      );
    });
  });

  describe('fetchThread', () => {
    it('should fetch single thread by slug', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => mockThread,
      });

      // Act
      const result = await fetchThread('how-to-care-for-succulents');

      // Assert
      expect(result).toEqual(mockThread);
    });
  });

  describe('createThread', () => {
    it('should create new thread with valid data', async () => {
      // Arrange
      const input: CreateThreadInput = {
        title: 'New Thread',
        category: 'plant-care',
        excerpt: 'Thread excerpt',
        first_post_content: 'First post content',
        first_post_format: 'markdown',
      };
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => mockThread,
      });

      // Act
      const result = await createThread(input);

      // Assert
      expect(result).toEqual(mockThread);
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/threads/'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify(input),
        })
      );
    });

    it('should validate CSRF token on create', async () => {
      // Arrange
      const input: CreateThreadInput = {
        title: 'New Thread',
        category: 'plant-care',
        excerpt: 'Thread excerpt',
        first_post_content: 'First post content',
      };
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => mockThread,
      });

      // Act
      await createThread(input);

      // Assert
      const fetchCall = fetchMock.mock.calls[0];
      const headers = fetchCall[1].headers;
      expect(headers['X-CSRFToken']).toBe('test-csrf-token');
    });

    it('should handle trust level restrictions (403)', async () => {
      // Arrange
      const input: CreateThreadInput = {
        title: 'New Thread',
        category: 'plant-care',
        excerpt: 'Thread excerpt',
        first_post_content: 'First post content',
      };
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 403,
        json: async () => ({ detail: 'Trust level too low' }),
      });

      // Act & Assert
      await expect(createThread(input)).rejects.toThrow('Trust level too low');
    });
  });

  // ============================================================================
  // POST TESTS
  // ============================================================================

  describe('fetchPosts', () => {
    it('should fetch posts for a thread', async () => {
      // Arrange
      const response = {
        results: [mockPost],
        count: 1,
        next: null,
        previous: null,
      };
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => response,
      });

      // Act
      const result = await fetchPosts({ thread: 'thread-123' });

      // Assert
      expect(result.items).toEqual([mockPost]);
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('thread=thread-123'),
        expect.any(Object)
      );
    });

    it('should throw error if thread is missing', async () => {
      // Act & Assert
      await expect(fetchPosts({ thread: '' })).rejects.toThrow(
        'Thread slug is required'
      );
    });

    it('should paginate post results', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ results: [mockPost], count: 50 }),
      });

      // Act
      await fetchPosts({ thread: 'thread-123', page: 2, limit: 10 });

      // Assert
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('page=2'),
        expect.any(Object)
      );
    });
  });

  describe('createPost', () => {
    it('should create new post with content', async () => {
      // Arrange
      const input: CreatePostInput = {
        thread: 'thread-123',
        content_raw: 'Test post content',
        content_format: 'markdown',
      };
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => mockPost,
      });

      // Act
      const result = await createPost(input);

      // Assert
      expect(result).toEqual(mockPost);
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/posts/'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify(input),
        })
      );
    });

    it('should handle spam detection errors (429)', async () => {
      // Arrange
      const input: CreatePostInput = {
        thread: 'thread-123',
        content_raw: 'Spam content',
      };
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 429,
        json: async () => ({ detail: 'Spam detected' }),
      });

      // Act & Assert
      await expect(createPost(input)).rejects.toThrow('Spam detected');
    });

    it('should handle rate limiting (429)', async () => {
      // Arrange
      const input: CreatePostInput = {
        thread: 'thread-123',
        content_raw: 'Test content',
      };
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 429,
        json: async () => ({ detail: 'Rate limit exceeded' }),
      });

      // Act & Assert
      await expect(createPost(input)).rejects.toThrow('Rate limit exceeded');
    });
  });

  describe('updatePost', () => {
    it('should update existing post', async () => {
      // Arrange
      const update: UpdatePostInput = {
        content_raw: 'Updated content',
        content_format: 'markdown',
      };
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ ...mockPost, content_raw: 'Updated content' }),
      });

      // Act
      const result = await updatePost('post-123', update);

      // Assert
      expect(result.content_raw).toBe('Updated content');
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/posts/post-123/'),
        expect.objectContaining({
          method: 'PATCH',
        })
      );
    });
  });

  describe('deletePost', () => {
    it('should soft delete post by UUID', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => undefined,
      });

      // Act
      await deletePost('post-123');

      // Assert
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/posts/post-123/'),
        expect.objectContaining({
          method: 'DELETE',
        })
      );
    });
  });

  // ============================================================================
  // REACTION TESTS
  // ============================================================================

  describe('addReaction', () => {
    it('should add reaction to post', async () => {
      // Arrange
      const input: AddReactionInput = {
        post: 'post-123',
        reaction_type: 'like',
      };
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => mockReaction,
      });

      // Act
      const result = await addReaction(input);

      // Assert
      expect(result).toEqual(mockReaction);
    });
  });

  describe('removeReaction', () => {
    it('should remove reaction by ID', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => undefined,
      });

      // Act
      await removeReaction('reaction-123');

      // Assert
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/reactions/reaction-123/'),
        expect.objectContaining({
          method: 'DELETE',
        })
      );
    });
  });

  describe('fetchReactions', () => {
    it('should fetch reactions for a post', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => [mockReaction],
      });

      // Act
      const result = await fetchReactions('post-123');

      // Assert
      expect(result).toEqual([mockReaction]);
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('post=post-123'),
        expect.any(Object)
      );
    });
  });

  // ============================================================================
  // SEARCH TESTS
  // ============================================================================

  describe('searchForum', () => {
    it('should search threads and posts by query', async () => {
      // Arrange
      const options: SearchForumOptions = {
        q: 'succulents',
        page: 1,
        page_size: 20,
      };
      const response = {
        threads: [mockThread],
        posts: [mockPost],
        meta: { count: 2, next: null, previous: null },
      };
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => response,
      });

      // Act
      const result = await searchForum(options);

      // Assert
      expect(result.threads).toEqual([mockThread]);
      expect(result.posts).toEqual([mockPost]);
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('q=succulents'),
        expect.any(Object)
      );
    });

    it('should throw error for empty query', async () => {
      // Act & Assert
      await expect(searchForum({ q: '' })).rejects.toThrow(
        'Search query is required'
      );
      await expect(searchForum({ q: '   ' })).rejects.toThrow(
        'Search query is required'
      );
    });

    it('should filter search by category', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ threads: [], posts: [], meta: { count: 0 } }),
      });

      // Act
      await searchForum({ q: 'test', category: 'plant-care' });

      // Assert
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('category=plant-care'),
        expect.any(Object)
      );
    });

    it('should filter search by author', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ threads: [], posts: [], meta: { count: 0 } }),
      });

      // Act
      await searchForum({ q: 'test', author: 'testuser' });

      // Assert
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('author=testuser'),
        expect.any(Object)
      );
    });

    it('should filter search by date range', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ threads: [], posts: [], meta: { count: 0 } }),
      });

      // Act
      await searchForum({
        q: 'test',
        date_from: '2025-01-01',
        date_to: '2025-01-31',
      });

      // Assert
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('date_from=2025-01-01'),
        expect.any(Object)
      );
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('date_to=2025-01-31'),
        expect.any(Object)
      );
    });
  });

  // ============================================================================
  // IMAGE UPLOAD TESTS
  // ============================================================================

  describe('uploadPostImage', () => {
    it('should upload image file to post', async () => {
      // Arrange
      const file = new File(['image data'], 'test.jpg', { type: 'image/jpeg' });
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => mockAttachment,
      });

      // Act
      const result = await uploadPostImage('post-123', file);

      // Assert
      expect(result).toEqual(mockAttachment);
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/posts/post-123/upload_image/'),
        expect.objectContaining({
          method: 'POST',
          credentials: 'include',
        })
      );
      // Verify FormData was sent (body should be FormData instance)
      const fetchCall = fetchMock.mock.calls[0];
      expect(fetchCall[1].body).toBeInstanceOf(FormData);
    });

    it('should validate CSRF token on upload', async () => {
      // Arrange
      const file = new File(['image data'], 'test.jpg', { type: 'image/jpeg' });
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => mockAttachment,
      });

      // Act
      await uploadPostImage('post-123', file);

      // Assert
      const fetchCall = fetchMock.mock.calls[0];
      const headers = fetchCall[1].headers;
      expect(headers['X-CSRFToken']).toBe('test-csrf-token');
    });

    it('should handle file size validation errors', async () => {
      // Arrange
      const file = new File(['image data'], 'test.jpg', { type: 'image/jpeg' });
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: async () => ({ detail: 'File size exceeds 5MB limit' }),
      });

      // Act & Assert
      await expect(uploadPostImage('post-123', file)).rejects.toThrow(
        'File size exceeds 5MB limit'
      );
    });

    it('should handle max attachment count errors', async () => {
      // Arrange
      const file = new File(['image data'], 'test.jpg', { type: 'image/jpeg' });
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: async () => ({ detail: 'Maximum 6 images per post' }),
      });

      // Act & Assert
      await expect(uploadPostImage('post-123', file)).rejects.toThrow(
        'Maximum 6 images per post'
      );
    });

    it('should handle invalid file type errors', async () => {
      // Arrange
      const file = new File(['pdf data'], 'test.pdf', { type: 'application/pdf' });
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: async () => ({ detail: 'Invalid file type' }),
      });

      // Act & Assert
      await expect(uploadPostImage('post-123', file)).rejects.toThrow(
        'Invalid file type'
      );
    });

    it('should handle upload failure without JSON response', async () => {
      // Arrange
      const file = new File(['image data'], 'test.jpg', { type: 'image/jpeg' });
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => {
          throw new Error('Not JSON');
        },
      });

      // Act & Assert
      await expect(uploadPostImage('post-123', file)).rejects.toThrow('Upload failed');
    });
  });

  describe('deletePostImage', () => {
    it('should delete image from post', async () => {
      // Arrange
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => undefined,
      });

      // Act
      await deletePostImage('post-123', 'attach-123');

      // Assert
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/posts/post-123/delete_image/attach-123/'),
        expect.objectContaining({
          method: 'DELETE',
        })
      );
    });
  });
});
