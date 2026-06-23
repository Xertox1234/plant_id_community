import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  fetchCategories,
  fetchCategory,
  fetchThreads,
  fetchThread,
  createThread,
  fetchPosts,
  createPost,
  updatePost,
  deletePost,
  toggleReaction,
  uploadPostImage,
  deletePostImage,
  searchForum,
} from './forumService';
import { clearCsrfToken } from '../utils/csrf';

// ---------------------------------------------------------------------------
// Backend fixture shapes (wagtail_forum contract)
// ---------------------------------------------------------------------------

const backendBoard = {
  id: 3,
  title: 'Plant Care',
  slug: 'plant-care',
  description: 'Tips',
  topic_count: 2,
  post_count: 9,
};

const backendTopicListItem = {
  id: 12,
  title: 'Succulent help',
  slug: 'succulent-help',
  author: 'jdoe',
  is_pinned: false,
  is_closed: false,
  reply_count: 4,
  view_count: 99,
  last_post_at: '2026-01-02T00:00:00Z',
  last_post_author: 'jdoe',
};

const backendTopicDetail = {
  id: 12,
  title: 'Succulent help',
  slug: 'succulent-help',
  board: { id: 3, slug: 'plant-care', title: 'Plant Care' },
  author: 'jdoe',
  is_pinned: false,
  is_closed: false,
  locked: false,
  reply_count: 4,
  view_count: 99,
  created_at: '2026-01-01T00:00:00Z',
  last_post_at: '2026-01-02T00:00:00Z',
  last_post_author: 'jdoe',
  opening_post_id: 50,
};

const backendPost = {
  id: 50,
  topic_id: 12,
  author: { username: 'jdoe', display_name: 'Jane Doe', trust_level: 'member' },
  body: [{ type: 'paragraph', value: 'hello', id: 'blk-1' }],
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  edited_at: null,
  is_opening_post: false,
  status: 'live' as const,
  reaction_counts: {},
  can_edit: false,
  can_delete: false,
};

// ---------------------------------------------------------------------------
// Test harness
// ---------------------------------------------------------------------------

let fetchMock: ReturnType<typeof vi.fn>;
let cookie: string;

beforeEach(() => {
  fetchMock = vi.fn();
  global.fetch = fetchMock as unknown as typeof fetch;
  cookie = 'csrftoken=test-csrf-token';
  Object.defineProperty(document, 'cookie', {
    get: () => cookie,
    set: (v: string) => {
      cookie = v;
    },
    configurable: true,
  });
  clearCsrfToken();
  document.head.querySelector('meta[name="csrf-token"]')?.remove();
  const meta = document.createElement('meta');
  meta.setAttribute('name', 'csrf-token');
  meta.setAttribute('content', 'test-csrf-token');
  document.head.appendChild(meta);
  vi.clearAllMocks();
});

afterEach(() => {
  clearCsrfToken();
  document.head.querySelector('meta[name="csrf-token"]')?.remove();
  vi.restoreAllMocks();
});

function okJson(body: unknown) {
  return { ok: true, status: 200, json: async () => body };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('forumService (wagtail_forum API contract)', () => {
  // --- Categories (boards) --------------------------------------------------

  it('fetchCategories hits /boards/ and maps board→category', async () => {
    fetchMock.mockResolvedValueOnce(okJson({ results: [backendBoard] }));
    const result = await fetchCategories();
    expect(result[0]).toMatchObject({
      id: '3',
      name: 'Plant Care',
      slug: 'plant-care',
      thread_count: 2,
      post_count: 9,
    });
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/forum/boards/'),
      expect.objectContaining({ credentials: 'include' })
    );
  });

  it('fetchCategory resolves by integer id from /boards/', async () => {
    fetchMock.mockResolvedValueOnce(okJson({ results: [backendBoard] }));
    const c = await fetchCategory(3);
    expect(c.id).toBe('3');
    expect(c.slug).toBe('plant-care');
  });

  it('fetchCategory throws when id not found', async () => {
    fetchMock.mockResolvedValueOnce(okJson({ results: [backendBoard] }));
    await expect(fetchCategory(999)).rejects.toThrow('Category not found');
  });

  // --- Threads (topics) -----------------------------------------------------

  it('fetchThreads hits /boards/{board}/topics/ and maps list items', async () => {
    fetchMock.mockResolvedValueOnce(
      okJson({ results: [backendTopicListItem], next: null, previous: null })
    );
    const result = await fetchThreads({ board: 'plant-care' });
    expect(result.items[0]).toMatchObject({
      id: '12',
      title: 'Succulent help',
      post_count: 4,
      view_count: 99,
    });
    expect(result.meta.next).toBeNull();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/boards/plant-care/topics/'),
      expect.any(Object)
    );
  });

  it('fetchThreads throws when board is omitted', async () => {
    await expect(fetchThreads()).rejects.toThrow('A board slug is required');
  });

  it('fetchThreads uses cursor URL directly (absolute URL, no double-prefix)', async () => {
    // DRF cursor `next` is an absolute URL. authenticatedFetch passes the url
    // arg straight to fetch() with no base prepended — so the absolute URL
    // must reach fetch() unchanged.
    const absoluteCursor = 'http://localhost:8000/api/v1/forum/topics/12/posts/?cursor=abc123';
    fetchMock.mockResolvedValueOnce(
      okJson({ results: [backendTopicListItem], next: null, previous: null })
    );
    await fetchThreads({ board: 'plant-care', cursor: absoluteCursor });
    expect(fetchMock).toHaveBeenCalledWith(absoluteCursor, expect.any(Object));
  });

  // --- Thread detail --------------------------------------------------------

  it('fetchThread hits /topics/{id}/ and maps detail shape', async () => {
    fetchMock.mockResolvedValueOnce(okJson(backendTopicDetail));
    const t = await fetchThread(12);
    expect(t).toMatchObject({
      id: '12',
      title: 'Succulent help',
      post_count: 4,
    });
    expect(t.category).toMatchObject({ id: '3', slug: 'plant-care' });
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/topics/12/'),
      expect.any(Object)
    );
  });

  // --- Posts ----------------------------------------------------------------

  it('fetchPosts hits /topics/{id}/posts/ and maps posts', async () => {
    fetchMock.mockResolvedValueOnce(okJson({ results: [backendPost], next: null, previous: null }));
    const result = await fetchPosts({ thread: 12 });
    expect(result.items[0]).toMatchObject({ id: '50', thread: '12' });
    expect(result.items[0].body).toHaveLength(1);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/topics/12/posts/'),
      expect.any(Object)
    );
  });

  it('fetchPosts uses absolute cursor URL directly (no double-prefix)', async () => {
    const absoluteCursor = 'http://localhost:8000/api/v1/forum/topics/12/posts/?cursor=xyz789';
    fetchMock.mockResolvedValueOnce(okJson({ results: [backendPost], next: null, previous: null }));
    await fetchPosts({ thread: 12, cursor: absoluteCursor });
    expect(fetchMock).toHaveBeenCalledWith(absoluteCursor, expect.any(Object));
  });

  it('fetchPosts throws when thread is missing', async () => {
    // @ts-expect-error — intentionally passing bad args to test runtime guard
    await expect(fetchPosts({})).rejects.toThrow('Thread id is required');
  });

  it('fetchPosts carries cursor links in meta', async () => {
    const nextUrl = 'http://localhost:8000/api/v1/forum/topics/12/posts/?cursor=next';
    fetchMock.mockResolvedValueOnce(
      okJson({ results: [backendPost], next: nextUrl, previous: null })
    );
    const result = await fetchPosts({ thread: 12 });
    expect(result.meta.next).toBe(nextUrl);
    expect(result.meta.previous).toBeNull();
  });

  // --- Search ---------------------------------------------------------------

  it('searchForum hits /search/?q= and maps topics→threads, posts→posts', async () => {
    fetchMock.mockResolvedValueOnce(
      okJson({
        topics: [{ id: 12, slug: 'succulent-help', title: 'Succulent help' }],
        posts: [{ id: 50, topic_id: 12, topic_title: 'Succulent help', excerpt: 'hello' }],
      })
    );
    const r = await searchForum({ q: 'succ' });
    expect(r.threads[0].id).toBe('12');
    expect(r.posts[0].id).toBe('50');
    expect(r.posts[0].thread).toBe('12');
    expect(r.posts[0].content_raw).toBe('hello');
    expect(r.total_threads).toBe(1);
    expect(r.total_posts).toBe(1);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/search/?q=succ'),
      expect.any(Object)
    );
  });

  it('searchForum rejects empty queries', async () => {
    await expect(searchForum({ q: '   ' })).rejects.toThrow('Search query is required');
  });

  // --- Write functions (structurally intact, Phase 2) -----------------------

  it('createThread posts to /categories/{id}/topics/create/ (Phase 2 placeholder)', async () => {
    fetchMock.mockResolvedValueOnce(okJson({ topic: backendTopicDetail }));
    const t = await createThread({
      title: 'Succulent help',
      category: 3,
      first_post_content: 'hello',
      first_post_format: 'html',
    });
    expect(t.id).toBe('12');
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/categories/3/topics/create/');
    expect(opts.method).toBe('POST');
  });

  it('createPost posts to /posts/create/ and unwraps {data}', async () => {
    fetchMock.mockResolvedValueOnce(okJson({ message: 'ok', data: backendPost }));
    const p = await createPost({ thread: 12, content_raw: 'hi', content_format: 'html' });
    expect(p.id).toBe('50');
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/posts/create/');
    expect(JSON.parse(opts.body)).toMatchObject({ topic: 12, content: 'hi' });
  });

  it('createPost throws a clear error when the response is missing {data}', async () => {
    fetchMock.mockResolvedValueOnce(okJson({ message: 'ok', post: backendPost }));
    await expect(
      createPost({ thread: 12, content_raw: 'hi', content_format: 'html' })
    ).rejects.toThrow(/missing "data"/);
  });

  it('updatePost maps topic_id to thread', async () => {
    fetchMock.mockResolvedValueOnce(okJson({ data: { ...backendPost, topic_id: 77 } }));
    const p = await updatePost('50', { content_raw: '<p>edited</p>', content_format: 'html' });
    expect(p.thread).toBe('77');
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/posts/50/');
    expect(opts.method).toBe('PATCH');
  });

  it('deletePost hits the /delete/ suffix endpoint', async () => {
    fetchMock.mockResolvedValueOnce({ ok: true, status: 204, json: async () => undefined });
    await deletePost('50');
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/posts/50/delete/'),
      expect.objectContaining({ method: 'DELETE' })
    );
  });

  it('toggleReaction posts {type} and returns {reaction_counts, reacted}', async () => {
    fetchMock.mockResolvedValueOnce(okJson({ reaction_counts: { like: 3 }, reacted: true }));
    const r = await toggleReaction('50', 'like');
    expect(r).toEqual({ reaction_counts: { like: 3 }, reacted: true });
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/posts/50/reactions/');
    expect(opts.method).toBe('POST');
    expect(JSON.parse(opts.body)).toEqual({ type: 'like' });
  });

  it('uploadPostImage sends FormData with the plural field name to images/upload/', async () => {
    const file = new File(['x'], 'a.jpg', { type: 'image/jpeg' });
    fetchMock.mockResolvedValueOnce(
      okJson({
        images: [
          { id: 7, image_url: 'http://x/a.jpg', thumbnail_url: 'http://x/t.jpg', upload_order: 0 },
        ],
      })
    );
    const a = await uploadPostImage('50', file);
    expect(a).toMatchObject({ id: '7', image_url: 'http://x/a.jpg', display_order: 0 });
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/posts/50/images/upload/');
    expect(opts.body).toBeInstanceOf(FormData);
    expect((opts.body as FormData).has('images')).toBe(true);
  });

  it('deletePostImage hits the images/{id}/delete/ endpoint', async () => {
    fetchMock.mockResolvedValueOnce({ ok: true, status: 204, json: async () => undefined });
    await deletePostImage('50', '7');
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/posts/50/images/7/delete/'),
      expect.objectContaining({ method: 'DELETE' })
    );
  });

  // --- Error propagation ----------------------------------------------------

  it('propagates backend errors with detail', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 429,
      json: async () => ({ detail: 'Rate limit exceeded' }),
    });
    await expect(createPost({ thread: 12, content_raw: 'x' })).rejects.toThrow(
      'Rate limit exceeded'
    );
  });

  it('propagates backend errors with canonical message field', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 403,
      json: async () => ({ message: 'Permission denied' }),
    });
    await expect(createPost({ thread: 12, content_raw: 'x' })).rejects.toThrow('Permission denied');
  });
});
