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
  subscribeToTopic,
  markSolution,
  clearSolution,
  unsubscribeFromTopic,
  blockUser,
  unblockUser,
  fetchBlockedUsers,
  fetchMyForumProfile,
  updateMyForumProfile,
  uploadPostImage,
  searchForum,
  searchForumUsers,
  improveDraft,
  askPlantCare,
  reportPlantCareAnswer,
  RagError,
  ComposeAssistError,
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
  locked: false,
  reply_count: 4,
  view_count: 99,
  last_post_at: '2026-01-02T00:00:00Z',
  last_post_author: 'jdoe',
  is_unread: false,
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
  is_subscribed: true,
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

// GET/PATCH me/profile/ (MeProfileSerializer). `avatar_id`/`fcm_token` are
// write-only and never appear in a response.
const backendMyProfile = {
  display_name: 'Jane Doe',
  bio: '',
  signature: '',
  title: '',
  trust_level: 1,
  post_count: 3,
  capabilities: { can_react: true, can_reply: true, can_create_topic: true },
  avatar: null,
  digest_frequency: 'off',
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

  it('fetchThreads appends ?sort= when a sort is provided (filter alters the request)', async () => {
    fetchMock.mockResolvedValueOnce(
      okJson({ results: [backendTopicListItem], next: null, previous: null })
    );
    await fetchThreads({ board: 'plant-care', sort: '-view_count' });
    const [url] = fetchMock.mock.calls[0];
    expect(url).toContain('/boards/plant-care/topics/?sort=-view_count');
  });

  it('fetchThreads omits ?sort= when no sort is provided', async () => {
    fetchMock.mockResolvedValueOnce(
      okJson({ results: [backendTopicListItem], next: null, previous: null })
    );
    await fetchThreads({ board: 'plant-care' });
    const [url] = fetchMock.mock.calls[0];
    expect(url).not.toContain('sort=');
  });

  it('fetchThreads does not append ?sort= onto an absolute cursor URL', async () => {
    // The cursor already encodes the active ordering server-side, so a cursor
    // request must pass through unchanged (no double sort param).
    const absoluteCursor =
      'http://localhost:8000/api/v1/forum/boards/plant-care/topics/?cursor=abc';
    fetchMock.mockResolvedValueOnce(
      okJson({ results: [backendTopicListItem], next: null, previous: null })
    );
    await fetchThreads({ board: 'plant-care', cursor: absoluteCursor, sort: '-view_count' });
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
      is_subscribed: true,
    });
    expect(t.category).toMatchObject({ id: '3', slug: 'plant-care' });
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/topics/12/'),
      expect.any(Object)
    );
  });

  it('fetchThread peek reads append ?peek=1 (no view count / read marker, todo 346)', async () => {
    fetchMock.mockResolvedValueOnce(okJson(backendTopicDetail));
    await fetchThread(12, { peek: true });
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/topics\/12\/\?peek=1$/),
      expect.any(Object)
    );
    fetchMock.mockResolvedValueOnce(okJson(backendTopicDetail));
    await fetchThread(12);
    expect(fetchMock).toHaveBeenLastCalledWith(
      expect.stringMatching(/\/topics\/12\/$/),
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
        topics: [
          {
            id: 12,
            slug: 'succulent-help',
            title: 'Succulent help',
            reply_count: 4,
            view_count: 99,
            last_post_at: '2026-01-02T00:00:00Z',
            board_id: 3,
            board_slug: 'plant-care',
          },
        ],
        posts: [
          {
            id: 50,
            topic_id: 12,
            topic_title: 'Succulent help',
            topic_slug: 'succulent-help',
            board_id: 3,
            board_slug: 'plant-care',
            excerpt: 'hello',
          },
        ],
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

  it('searchForum sends the category as ?board= and total_threads matches array length', async () => {
    fetchMock.mockResolvedValueOnce(
      okJson({
        topics: [
          {
            id: 31,
            slug: 'tomato-blight',
            title: 'Blight-resistant tomatoes',
            reply_count: 3,
            view_count: 12,
            last_post_at: '2026-07-01T10:00:00Z',
            board_id: 54,
            board_slug: 'general-discussion',
          },
        ],
        posts: [],
      })
    );
    const r = await searchForum({ q: 'tomato', category: 'general-discussion' });
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('board=general-discussion'),
      expect.any(Object)
    );
    expect(r.total_threads).toBe(r.threads.length);
    expect(r.total_threads).toBe(1);
  });

  it('searchForum sends ?page= only when page > 1', async () => {
    fetchMock.mockResolvedValueOnce(okJson({ topics: [], posts: [] }));
    await searchForum({ q: 'succ', page: 2 });
    expect(fetchMock.mock.calls[0][0]).toContain('page=2');

    fetchMock.mockResolvedValueOnce(okJson({ topics: [], posts: [] }));
    await searchForum({ q: 'succ', page: 1 });
    expect(fetchMock.mock.calls[1][0]).not.toContain('page=');
  });

  it('searchForum parses topics_has_more/posts_has_more into has_more flags', async () => {
    fetchMock.mockResolvedValueOnce(
      okJson({ topics: [], posts: [], topics_has_more: true, posts_has_more: false })
    );
    const r = await searchForum({ q: 'succ' });
    expect(r.has_more_threads).toBe(true);
    expect(r.has_more_posts).toBe(false);
  });

  it('searchForum defaults has_more flags to false when the backend omits them', async () => {
    fetchMock.mockResolvedValueOnce(okJson({ topics: [], posts: [] }));
    const r = await searchForum({ q: 'succ' });
    expect(r.has_more_threads).toBe(false);
    expect(r.has_more_posts).toBe(false);
  });

  // --- Write functions (structurally intact, Phase 2) -----------------------

  it('createThread posts to /boards/{slug}/topics/ with {title, slug, body[]}', async () => {
    fetchMock.mockResolvedValueOnce(
      okJson({ id: 12, slug: 'succulent-help', status: 'published' })
    );
    const r = await createThread({
      boardSlug: 'plant-care',
      title: 'Succulent help!',
      content: '<p>hi</p>',
    });
    expect(r).toEqual({ id: '12', slug: 'succulent-help', status: 'published' });
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/boards/plant-care/topics/');
    expect(opts.method).toBe('POST');
    expect(JSON.parse(opts.body)).toEqual({
      title: 'Succulent help!',
      slug: 'succulent-help',
      body: [{ type: 'paragraph', value: '<p>hi</p>' }],
    });
  });

  it('createThread nests an identification snapshot when one is attached (M6)', async () => {
    fetchMock.mockResolvedValueOnce(okJson({ id: 12, slug: 'what-is-this', status: 'published' }));
    const identification = {
      image_id: 42,
      provider: 'plant_id',
      candidates: [
        { name: 'Swiss cheese plant', scientific_name: 'Monstera deliciosa', confidence: 0.82 },
      ],
    };
    await createThread({
      boardSlug: 'plant-care',
      title: 'What is this?',
      content: '<p>hi</p>',
      identification,
    });
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      title: 'What is this?',
      slug: 'what-is-this',
      body: [{ type: 'paragraph', value: '<p>hi</p>' }],
      identification,
    });
  });

  it('createThread omits the identification key entirely when there is none', async () => {
    // The common compose must not gain a `"identification": null` on the wire.
    fetchMock.mockResolvedValueOnce(okJson({ id: 12, slug: 'plain', status: 'published' }));
    await createThread({
      boardSlug: 'plant-care',
      title: 'Plain',
      content: '<p>hi</p>',
      identification: null,
    });
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).not.toHaveProperty('identification');
  });

  it('createPost posts to /topics/{id}/posts/ with {body[]}', async () => {
    fetchMock.mockResolvedValueOnce(okJson({ id: 51, status: 'pending' }));
    const r = await createPost({ thread: 12, content: '<p>hi</p>' });
    expect(r).toEqual({ id: '51', status: 'pending' });
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/topics/12/posts/');
    expect(opts.method).toBe('POST');
    expect(JSON.parse(opts.body)).toEqual({ body: [{ type: 'paragraph', value: '<p>hi</p>' }] });
  });

  it('updatePost PATCHes /posts/{id}/ with {body[]} and returns {post, status}', async () => {
    fetchMock.mockResolvedValueOnce(
      okJson({ ...backendPost, id: 50, topic_id: 77, moderation_status: 'published' })
    );
    const r = await updatePost('50', { content: '<p>edited</p>' });
    expect(r.status).toBe('published');
    expect(r.post.id).toBe('50');
    expect(r.post.thread).toBe('77');
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/posts/50/');
    expect(opts.method).toBe('PATCH');
    expect(JSON.parse(opts.body)).toEqual({
      body: [{ type: 'paragraph', value: '<p>edited</p>' }],
    });
  });

  it('deletePost DELETEs /posts/{id}/ (no /delete/ suffix)', async () => {
    fetchMock.mockResolvedValueOnce({ ok: true, status: 204, json: async () => undefined });
    await deletePost('50');
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/posts\/50\/$/);
    expect(opts.method).toBe('DELETE');
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

  it('subscribeToTopic POSTs to /topics/{id}/subscription/', async () => {
    fetchMock.mockResolvedValueOnce(okJson({ subscribed: true }));
    await subscribeToTopic(12);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/topics/12/subscription/');
    expect(opts.method).toBe('POST');
  });

  it('unsubscribeFromTopic DELETEs /topics/{id}/subscription/', async () => {
    fetchMock.mockResolvedValueOnce(okJson({ subscribed: false }));
    await unsubscribeFromTopic(12);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/topics/12/subscription/');
    expect(opts.method).toBe('DELETE');
  });

  it('blockUser POSTs to /users/{username}/block/ (todo 284/M9)', async () => {
    fetchMock.mockResolvedValueOnce(okJson({ blocked: true }));
    await blockUser('noisy-neighbor');
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/users/noisy-neighbor/block/');
    expect(opts.method).toBe('POST');
  });

  it('unblockUser DELETEs /users/{username}/block/', async () => {
    fetchMock.mockResolvedValueOnce(okJson({ blocked: false }));
    await unblockUser('noisy-neighbor');
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/users/noisy-neighbor/block/');
    expect(opts.method).toBe('DELETE');
  });

  it('fetchBlockedUsers GETs /me/blocks/', async () => {
    fetchMock.mockResolvedValueOnce(
      okJson([
        {
          username: 'noisy-neighbor',
          display_name: 'Noisy Neighbor',
          avatar: null,
          trust_level: 1,
          title: '',
          blocked_at: '2026-08-01T00:00:00Z',
        },
      ])
    );
    const result = await fetchBlockedUsers();
    const [url] = fetchMock.mock.calls[0];
    expect(url).toContain('/me/blocks/');
    expect(result).toHaveLength(1);
    expect(result[0].username).toBe('noisy-neighbor');
  });

  it('fetchMyForumProfile GETs /me/profile/ (todo 340)', async () => {
    fetchMock.mockResolvedValueOnce(okJson(backendMyProfile));
    const result = await fetchMyForumProfile();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain('/me/profile/');
    expect(init.method).toBeUndefined(); // GET
    expect(result.digest_frequency).toBe('off');
    expect(result.display_name).toBe('Jane Doe');
  });

  it('updateMyForumProfile PATCHes /me/profile/ with a JSON body and returns the updated profile', async () => {
    fetchMock.mockResolvedValueOnce(okJson({ ...backendMyProfile, digest_frequency: 'weekly' }));
    const result = await updateMyForumProfile({ digest_frequency: 'weekly' });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain('/me/profile/');
    expect(init.method).toBe('PATCH');
    expect(JSON.parse(init.body)).toEqual({ digest_frequency: 'weekly' });
    expect(init.credentials).toBe('include');
    expect(init.headers['X-CSRFToken']).toBe('test-csrf-token');
    expect(result.digest_frequency).toBe('weekly');
  });

  it('markSolution POSTs the post id to /topics/{id}/solution/', async () => {
    fetchMock.mockResolvedValueOnce(
      okJson({ is_solved: true, solved_post_id: 77, solved_at: '2026-07-31T10:00:00Z' })
    );
    const result = await markSolution(12, 77);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/topics/12/solution/');
    expect(opts.method).toBe('POST');
    expect(JSON.parse(opts.body)).toEqual({ post_id: 77 });
    expect(result.solved_post_id).toBe(77);
  });

  it('clearSolution DELETEs /topics/{id}/solution/', async () => {
    fetchMock.mockResolvedValueOnce(
      okJson({ is_solved: false, solved_post_id: null, solved_at: null })
    );
    const result = await clearSolution(12);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/topics/12/solution/');
    expect(opts.method).toBe('DELETE');
    expect(result.is_solved).toBe(false);
  });

  it('searchForumUsers GETs /users/search/?q=<query>', async () => {
    fetchMock.mockResolvedValueOnce(okJson([{ username: 'alice', display_name: 'Alice' }]));
    const results = await searchForumUsers('ali');
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/users/search/?q=ali');
    expect(opts.method ?? 'GET').toBe('GET');
    expect(results).toEqual([{ username: 'alice', display_name: 'Alice' }]);
  });

  it('searchForumUsers URL-encodes the query', async () => {
    fetchMock.mockResolvedValueOnce(okJson([]));
    await searchForumUsers('a b');
    const [url] = fetchMock.mock.calls[0];
    expect(url).toContain('q=a%20b');
  });

  it('uploadPostImage POSTs FormData (field "image") to the topic-independent /images/ route', async () => {
    const file = new File(['x'], 'a.jpg', { type: 'image/jpeg' });
    fetchMock.mockResolvedValueOnce(
      okJson({ id: 7, url: 'http://x/a.jpg', alt: 'a.jpg', width: 800, height: 600 })
    );
    const img = await uploadPostImage(file);
    expect(img).toEqual({ id: 7, url: 'http://x/a.jpg', alt: 'a.jpg', width: 800, height: 600 });
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/api/v1/forum/images/');
    expect(opts.body).toBeInstanceOf(FormData);
    expect((opts.body as FormData).has('image')).toBe(true);
    // No alt argument → no alt part, so the request is byte-identical to the
    // pre-M7 shape.
    expect((opts.body as FormData).has('alt')).toBe(false);
  });

  it('uploadPostImage sends author-supplied alt text as an "alt" part (M7)', async () => {
    const file = new File(['x'], 'IMG_2481.jpg', { type: 'image/jpeg' });
    fetchMock.mockResolvedValueOnce(
      okJson({ id: 7, url: 'http://x/a.jpg', alt: 'A fern frond', width: 800, height: 600 })
    );
    await uploadPostImage(file, '  A fern frond  ');
    const [, opts] = fetchMock.mock.calls[0];
    // Trimmed on the way out — the backend strips too, but sending clean data
    // keeps the stored value and the echoed value identical.
    expect((opts.body as FormData).get('alt')).toBe('A fern frond');
  });

  it('uploadPostImage omits the alt part when the author skipped it (M7)', async () => {
    const file = new File(['x'], 'a.jpg', { type: 'image/jpeg' });
    fetchMock.mockResolvedValueOnce(
      okJson({ id: 7, url: 'http://x/a.jpg', alt: '', width: 800, height: 600 })
    );
    await uploadPostImage(file, '   ');
    const [, opts] = fetchMock.mock.calls[0];
    // Whitespace-only is "no description", not a description made of spaces.
    expect((opts.body as FormData).has('alt')).toBe(false);
  });

  // --- Error propagation ----------------------------------------------------

  it('propagates backend errors with detail', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 429,
      json: async () => ({ detail: 'Rate limit exceeded' }),
    });
    await expect(createPost({ thread: 12, content: 'x' })).rejects.toThrow('Rate limit exceeded');
  });

  it('propagates backend errors with canonical message field', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 403,
      json: async () => ({ message: 'Permission denied' }),
    });
    await expect(createPost({ thread: 12, content: 'x' })).rejects.toThrow('Permission denied');
  });

  // --- AI composer assist (todo 275 / M14) ----------------------------------

  it('improveDraft posts the draft and returns the trimmed rewrite', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ text: '  Improved copy.  ' }),
    });
    await expect(improveDraft('<p>draft</p>')).resolves.toBe('Improved copy.');
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain('/api/v1/forum/compose/assist/');
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body)).toEqual({ text: '<p>draft</p>' });
    // Mutating request → CSRF header + cookie auth (web/CLAUDE.md convention).
    expect(init.headers['X-CSRFToken']).toBe('test-csrf-token');
    expect(init.credentials).toBe('include');
  });

  it('improveDraft marks only 403 and code:disabled as permanent', async () => {
    // A bare 503 must NOT be permanent: the endpoint returns it for a provider
    // error, a timeout and an empty completion as well as for the feature flag
    // being off, so latching on the status disabled the button on the first blip
    // (todo 275 code review). The `code` is the discriminator.
    for (const [status, code, permanent] of [
      [403, undefined, true], // not a premium account
      [503, 'disabled', true], // deployment has the feature off
      [503, 'unavailable', false], // provider error / timeout / empty completion
      [503, undefined, false], // unlabelled 503 → assume transient, don't give up
      [429, undefined, false], // at capacity, retry later
      [400, undefined, false], // bad draft
    ] as const) {
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status,
        json: async () => ({ detail: `failed ${status}`, ...(code && { code }) }),
      });
      await expect(improveDraft('<p>draft</p>')).rejects.toMatchObject({
        name: 'ComposeAssistError',
        status,
        code,
        permanent,
        message: `failed ${status}`,
      });
    }
  });

  it('improveDraft rejects an empty rewrite rather than blanking the draft', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ text: '   ' }),
    });
    await expect(improveDraft('<p>draft</p>')).rejects.toBeInstanceOf(ComposeAssistError);
  });

  // --- RAG plant-care answers (todo 289 / M13) --------------------------------

  it('askPlantCare posts the question with CSRF + cookie auth and returns the envelope', async () => {
    const envelope = {
      status: 'no_information',
      answer_id: null,
      sources: [],
    };
    fetchMock.mockResolvedValueOnce(okJson(envelope));
    await expect(askPlantCare('how often should I water a pothos')).resolves.toEqual(envelope);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain('/api/v1/forum/care/ask/');
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body)).toEqual({ question: 'how often should I water a pothos' });
    expect(init.headers['X-CSRFToken']).toBe('test-csrf-token');
    expect(init.credentials).toBe('include');
  });

  it('askPlantCare marks 401, 403 and code:disabled as permanent — never a bare 503', async () => {
    // Same contract as compose assist, plus 401: the search page is PUBLIC, so
    // an anonymous visitor sees the affordance and the server's 401 teaches.
    for (const [status, code, permanent] of [
      [401, undefined, true], // not signed in
      [403, undefined, true], // not a premium account
      [503, 'disabled', true], // deployment has the feature off
      [503, 'unavailable', false], // provider / retrieval blip — transient
      [503, undefined, false], // unlabelled 503 → assume transient
      [429, undefined, false], // throttle or budget, retry later
      [400, undefined, false], // bad question
    ] as const) {
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status,
        json: async () => ({ detail: `failed ${status}`, ...(code && { code }) }),
      });
      await expect(askPlantCare('q')).rejects.toMatchObject({
        name: 'RagError',
        status,
        code,
        permanent,
        message: `failed ${status}`,
      });
    }
  });

  it('askPlantCare rejects an envelope without a known status', async () => {
    fetchMock.mockResolvedValueOnce(okJson({ status: 'surprise' }));
    await expect(askPlantCare('q')).rejects.toBeInstanceOf(RagError);
  });

  it('reportPlantCareAnswer posts the detail to the answer route', async () => {
    fetchMock.mockResolvedValueOnce(okJson({ reported: true }));
    await expect(
      reportPlantCareAnswer(42, 'Pothos should not be watered daily')
    ).resolves.toBeUndefined();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain('/api/v1/forum/care/answers/42/report/');
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body)).toEqual({ detail: 'Pothos should not be watered daily' });
    expect(init.headers['X-CSRFToken']).toBe('test-csrf-token');
  });
});
