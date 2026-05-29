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
  fetchReactions,
  uploadPostImage,
  deletePostImage,
  searchForum,
} from './forumService';
import { clearCsrfToken } from '../utils/csrf';

const backendUser = { id: 1, username: 'jdoe', first_name: 'Jane', last_name: 'Doe' };
const backendForum = {
  id: 3,
  name: 'Plant Care',
  description: 'Tips',
  topics_count: 2,
  posts_count: 9,
  last_activity: '2026-01-02T00:00:00Z',
};
const backendTopic = {
  id: 12,
  subject: 'Succulent help',
  poster: backendUser,
  forum: { id: 3, name: 'Plant Care', slug: 'plant-care' },
  created: '2026-01-01T00:00:00Z',
  posts_count: 5,
  last_post_on: '2026-01-02T00:00:00Z',
  replies_count: 4,
  views_count: 99,
};
const backendPost = {
  id: 50,
  content: '<p>hello</p>',
  poster: backendUser,
  created: '2026-01-01T00:00:00Z',
  updated: '2026-01-01T00:00:00Z',
  content_format: 'html',
  topic_id: 12,
};

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

describe('forumService (translation layer)', () => {
  it('fetchCategories unwraps DRF results and maps fields', async () => {
    fetchMock.mockResolvedValueOnce(okJson({ results: [backendForum], count: 1 }));
    const result = await fetchCategories();
    expect(result[0]).toMatchObject({
      id: '3',
      name: 'Plant Care',
      thread_count: 2,
      post_count: 9,
    });
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/forum/categories/'),
      expect.objectContaining({ credentials: 'include' })
    );
  });

  it('fetchCategory resolves by integer id from the list', async () => {
    fetchMock.mockResolvedValueOnce(okJson({ results: [backendForum], count: 1 }));
    const c = await fetchCategory(3);
    expect(c.id).toBe('3');
  });

  it('fetchThreads hits the category topics endpoint and maps topics->threads', async () => {
    fetchMock.mockResolvedValueOnce(
      okJson({ results: [backendTopic], count: 1, next: null, previous: null })
    );
    const result = await fetchThreads({ category: 3, page: 1 });
    expect(result.items[0]).toMatchObject({ id: '12', title: 'Succulent help', post_count: 5 });
    expect(result.meta.count).toBe(1);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/categories/3/topics/?page=1'),
      expect.any(Object)
    );
  });

  it('fetchThreads without category hits /topics/', async () => {
    fetchMock.mockResolvedValueOnce(okJson({ results: [backendTopic], count: 1 }));
    await fetchThreads({ page: 2 });
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/topics/?page=2'),
      expect.any(Object)
    );
  });

  it('fetchThread unwraps {topic} from the detail endpoint', async () => {
    fetchMock.mockResolvedValueOnce(
      okJson({ topic: backendTopic, posts: { results: [], count: 0 } })
    );
    const t = await fetchThread(12);
    expect(t).toMatchObject({ id: '12', title: 'Succulent help' });
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/topics/12/'),
      expect.any(Object)
    );
  });

  it('createThread posts subject/content to the create endpoint', async () => {
    fetchMock.mockResolvedValueOnce(
      okJson({ message: 'ok', topic: backendTopic, first_post_id: 50 })
    );
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
    expect(JSON.parse(opts.body)).toMatchObject({ subject: 'Succulent help', content: 'hello' });
  });

  it('fetchPosts queries by topic id and maps posts', async () => {
    fetchMock.mockResolvedValueOnce(okJson({ results: [backendPost], count: 1 }));
    const result = await fetchPosts({ thread: 12, page: 1 });
    expect(result.items[0]).toMatchObject({ id: '50', thread: '12', content_raw: '<p>hello</p>' });
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('topic=12'), expect.any(Object));
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
    // Defensive guard (todo 111): the old {message, post} shape (no `data`) must
    // throw clearly rather than crash inside mapPostToPost on undefined.id.
    fetchMock.mockResolvedValueOnce(okJson({ message: 'ok', post: backendPost }));
    await expect(
      createPost({ thread: 12, content_raw: 'hi', content_format: 'html' })
    ).rejects.toThrow(/missing "data"/);
  });

  it('updatePost maps topic_id to a non-empty thread (todo 112)', async () => {
    fetchMock.mockResolvedValueOnce(
      okJson({ message: 'ok', data: { ...backendPost, content: '<p>edited</p>', topic_id: 77 } })
    );
    const p = await updatePost('50', { content_raw: '<p>edited</p>', content_format: 'html' });
    expect(p.content_raw).toBe('<p>edited</p>');
    // todo 112: was '' (broken). Now the real topic id from the response.
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

  it('toggleReaction posts reaction_type and normalizes counts', async () => {
    fetchMock.mockResolvedValueOnce(
      okJson({
        success: true,
        action: 'added',
        reaction_type: 'like',
        reactions: { like: { count: 3, users: [] } },
        user_reactions: ['like'],
      })
    );
    const r = await toggleReaction('50', 'like');
    expect(r).toMatchObject({
      action: 'added',
      reaction_counts: { like: 3 },
      user_reactions: ['like'],
    });
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/posts/50/reactions/');
    expect(JSON.parse(opts.body)).toEqual({ reaction_type: 'like' });
  });

  it('fetchReactions normalizes counts and user_reactions', async () => {
    fetchMock.mockResolvedValueOnce(
      okJson({
        post_id: 50,
        reactions: { like: { count: 3, users: [] } },
        user_reactions: [],
        total_reactions: 3,
      })
    );
    const r = await fetchReactions('50');
    expect(r.reaction_counts).toEqual({ like: 3 });
  });

  it('uploadPostImage sends FormData with the plural field name to images/upload/', async () => {
    const file = new File(['x'], 'a.jpg', { type: 'image/jpeg' });
    fetchMock.mockResolvedValueOnce(
      okJson({
        message: 'ok',
        images: [
          { id: 7, image_url: 'http://x/a.jpg', thumbnail_url: 'http://x/t.jpg', upload_order: 0 },
        ],
        post_id: 50,
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

  it('searchForum maps topics->threads and posts->posts', async () => {
    fetchMock.mockResolvedValueOnce(
      okJson({ query: 'succ', topics: [backendTopic], posts: [backendPost] })
    );
    const r = await searchForum({ q: 'succ' });
    expect(r.threads[0].id).toBe('12');
    expect(r.posts[0].id).toBe('50');
    // todo 112: search posts get a real thread id from topic_id, not ''.
    expect(r.posts[0].thread).toBe('12');
    expect(r.total_threads).toBe(1);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/search/?q=succ'),
      expect.any(Object)
    );
  });

  it('searchForum rejects empty queries', async () => {
    await expect(searchForum({ q: '   ' })).rejects.toThrow('Search query is required');
  });

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
      json: async () => ({
        error: true,
        message: 'Permission denied',
        code: 'forbidden',
        status_code: 403,
      }),
    });
    await expect(createPost({ thread: 12, content_raw: 'x' })).rejects.toThrow('Permission denied');
  });
});
