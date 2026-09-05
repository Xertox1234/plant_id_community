import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  fetchBlogComments,
  addBlogComment,
  flagBlogComment,
  BLOG_COMMENT_MAX_LENGTH,
} from './blogCommentService';
import { ForumApiError } from './forumService';
import { clearCsrfToken } from '../utils/csrf';

const BASE = 'http://localhost:8000/api/v1/blog';

// DRF v1 BlogCommentSerializer shape (author = UserSerializer).
const author = {
  id: 2,
  username: 'june_park',
  first_name: 'June',
  last_name: 'Park',
  display_name: 'June Park',
  avatar_url: null,
};

const reply = {
  id: 12,
  post: 6,
  author,
  content: 'A reply',
  parent: 11,
  is_approved: true,
  is_reply: true,
  replies: [],
  created_at: '2026-09-05T10:00:00Z',
  updated_at: '2026-09-05T10:00:00Z',
};

const comment = {
  id: 11,
  post: 6,
  author,
  content: 'First!',
  parent: null,
  is_approved: true,
  is_reply: false,
  replies: [reply],
  created_at: '2026-09-05T09:00:00Z',
  updated_at: '2026-09-05T09:00:00Z',
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
});

afterEach(() => {
  clearCsrfToken();
  document.head.querySelector('meta[name="csrf-token"]')?.remove();
  vi.restoreAllMocks();
});

function okJson(body: unknown, status = 200) {
  return { ok: true, status, json: async () => body };
}

function failJson(status: number, body: unknown) {
  return { ok: false, status, json: async () => body };
}

describe('blogCommentService (DRF v1 blog comments, todo 352)', () => {
  it('exposes the client-side body cap', () => {
    expect(BLOG_COMMENT_MAX_LENGTH).toBe(2000);
  });

  it('fetchBlogComments GETs /posts/<id>/comments/ with credentials and returns the list verbatim', async () => {
    fetchMock.mockResolvedValueOnce(okJson([comment]));
    const list = await fetchBlogComments(6);
    expect(fetchMock.mock.calls[0][0]).toBe(`${BASE}/posts/6/comments/`);
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ credentials: 'include' });
    expect(fetchMock.mock.calls[0][1].method).toBeUndefined();
    expect(list).toEqual([comment]);
    expect(list[0].replies[0].parent).toBe(11);
  });

  it('fetchBlogComments surfaces the 403 for a post with comments disabled as a status-carrying error', async () => {
    // A plain `{detail}` Response, not the exception envelope.
    fetchMock.mockResolvedValueOnce(
      failJson(403, { detail: 'Comments are disabled for this post.' })
    );
    const err = await fetchBlogComments(6).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ForumApiError);
    expect((err as ForumApiError).status).toBe(403);
    expect((err as ForumApiError).message).toBe('Comments are disabled for this post.');
  });

  it('addBlogComment POSTs {content} to /posts/<id>/add_comment/ with CSRF and returns the created comment', async () => {
    fetchMock.mockResolvedValueOnce(okJson(comment, 201));
    const created = await addBlogComment(6, { content: 'First!' });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${BASE}/posts/6/add_comment/`);
    expect(init).toMatchObject({ method: 'POST', credentials: 'include' });
    expect(init.headers).toMatchObject({
      'Content-Type': 'application/json',
      'X-CSRFToken': 'test-csrf-token',
    });
    // `parent` is omitted (not sent as null) for a top-level comment.
    expect(JSON.parse(init.body)).toEqual({ content: 'First!' });
    expect(created).toEqual(comment);
  });

  it('addBlogComment sends `parent` for a reply', async () => {
    fetchMock.mockResolvedValueOnce(okJson(reply, 201));
    await addBlogComment(6, { content: 'A reply', parent: 11 });
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      content: 'A reply',
      parent: 11,
    });
  });

  it('addBlogComment encodes the post id in the URL', async () => {
    fetchMock.mockResolvedValueOnce(okJson(comment, 201));
    await addBlogComment(6, { content: 'x' });
    expect(fetchMock.mock.calls[0][0]).toBe(`${BASE}/posts/6/add_comment/`);
    fetchMock.mockResolvedValueOnce(okJson(comment, 201));
    await addBlogComment(42, { content: 'x' });
    expect(fetchMock.mock.calls[1][0]).toBe(`${BASE}/posts/42/add_comment/`);
  });

  it('addBlogComment maps the 429 envelope to a status-carrying error', async () => {
    // apps/core/exceptions.py's Ratelimited branch (429 + Retry-After).
    fetchMock.mockResolvedValueOnce(
      failJson(429, {
        error: true,
        message: 'Rate limit exceeded. Please try again later.',
        code: 'rate_limited',
        status_code: 429,
      })
    );
    const err = await addBlogComment(6, { content: 'x' }).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ForumApiError);
    expect((err as ForumApiError).status).toBe(429);
  });

  it('addBlogComment surfaces a flattened field error (400) with its message', async () => {
    // readable_message() flattens {parent: [...]} to "parent: <text>".
    fetchMock.mockResolvedValueOnce(
      failJson(400, {
        error: true,
        message: 'parent: That comment is awaiting moderation and cannot be replied to yet.',
        code: 'invalid',
        status_code: 400,
      })
    );
    const err = await addBlogComment(6, { content: 'x', parent: 11 }).catch((e: unknown) => e);
    expect((err as ForumApiError).status).toBe(400);
    expect((err as ForumApiError).message).toBe(
      'parent: That comment is awaiting moderation and cannot be replied to yet.'
    );
  });

  it('flagBlogComment POSTs to /comments/<id>/flag/ with CSRF and returns the detail', async () => {
    fetchMock.mockResolvedValueOnce(okJson({ detail: 'Comment has been flagged for review.' }));
    const result = await flagBlogComment(11);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${BASE}/comments/11/flag/`);
    expect(init).toMatchObject({ method: 'POST', credentials: 'include' });
    expect(init.headers).toMatchObject({ 'X-CSRFToken': 'test-csrf-token' });
    expect(result).toEqual({ detail: 'Comment has been flagged for review.' });
  });

  it('flagBlogComment surfaces the self-flag 400 detail', async () => {
    fetchMock.mockResolvedValueOnce(failJson(400, { detail: 'You cannot flag your own comment.' }));
    const err = await flagBlogComment(11).catch((e: unknown) => e);
    expect((err as ForumApiError).status).toBe(400);
    expect((err as ForumApiError).message).toBe('You cannot flag your own comment.');
  });

  it('falls back to an HTTP message when the error body is not JSON', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 502,
      json: async () => {
        throw new Error('not json');
      },
    });
    const err = await fetchBlogComments(6).catch((e: unknown) => e);
    expect((err as ForumApiError).status).toBe(502);
    expect((err as ForumApiError).message).toBe('Request failed');
  });
});
