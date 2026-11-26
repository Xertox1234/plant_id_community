/**
 * Retry safety of the forum and DM writes (audit F143, F144).
 *
 * F144: a create carries the compose action's Idempotency-Key, so a retry
 * after a lost response replays instead of posting twice.
 * F143: a 403 whose body is Django's "CSRF Failed: ..." (the stale token
 * after a login in another tab rotated the cookie) refreshes the token from
 * /api/csrf/ and retries exactly once, with the same Idempotency-Key. Any
 * other 403 (blocked, permission) is never retried.
 *
 * Real `Response` objects on purpose: a real body can be read once, and the
 * helper has to peek at a 403 without stealing it from the caller.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  createThread,
  createPost,
  updatePost,
  uploadPostImage,
  ForumApiError,
} from './forumService';
import { sendMessage, sendConversationMessage } from './messageService';
import { clearCsrfToken } from '../utils/csrf';

const BASE = 'http://localhost:8000/api/v1/forum';
const CSRF_URL = 'http://localhost:8000/api/csrf/';

let fetchMock: ReturnType<typeof vi.fn>;

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

// The envelope apps/core/exceptions.py builds around DRF's PermissionDenied
// raised by CookieJWTAuthentication.enforce_csrf.
const csrfFailed = () =>
  json(403, {
    error: true,
    message: "CSRF Failed: CSRF token from the 'X-Csrftoken' HTTP header incorrect.",
    code: 'permission_denied',
    status_code: 403,
    errors: { detail: 'CSRF Failed: CSRF token incorrect.' },
  });
const blocked = () =>
  json(403, {
    error: true,
    message: 'You cannot message this user.',
    code: 'permission_denied',
    status_code: 403,
  });

function headersOf(call: unknown[]): Record<string, string> {
  const init = (call[1] ?? {}) as RequestInit;
  return (init.headers ?? {}) as Record<string, string>;
}

/** The write attempts only — not the /api/csrf/ refetch. */
function writeCalls() {
  return fetchMock.mock.calls.filter((c) => c[0] !== CSRF_URL);
}

beforeEach(() => {
  fetchMock = vi.fn();
  global.fetch = fetchMock as unknown as typeof fetch;
  clearCsrfToken();
  // A STALE token in the meta tag: the refresh must not re-read it.
  document.head.querySelector('meta[name="csrf-token"]')?.remove();
  const meta = document.createElement('meta');
  meta.setAttribute('name', 'csrf-token');
  meta.setAttribute('content', 'stale-token');
  document.head.appendChild(meta);
});

afterEach(() => {
  clearCsrfToken();
  document.head.querySelector('meta[name="csrf-token"]')?.remove();
  vi.restoreAllMocks();
});

describe('Idempotency-Key on forum and DM writes (F144)', () => {
  it('createThread sends the given key as Idempotency-Key', async () => {
    fetchMock.mockResolvedValueOnce(json(201, { id: 9, slug: 't', status: 'published' }));
    await createThread({ boardSlug: 'b', title: 'T', body: [] }, 'key-topic');
    expect(headersOf(fetchMock.mock.calls[0])['Idempotency-Key']).toBe('key-topic');
  });

  it('createPost sends the given key as Idempotency-Key', async () => {
    fetchMock.mockResolvedValueOnce(json(201, { id: 3, status: 'published' }));
    await createPost({ thread: 12, body: [] }, 'key-reply');
    expect(headersOf(fetchMock.mock.calls[0])['Idempotency-Key']).toBe('key-reply');
  });

  it('updatePost sends the given key as Idempotency-Key (the backend replays edits, M35)', async () => {
    fetchMock.mockResolvedValueOnce(
      json(200, {
        id: 5,
        topic_id: 12,
        body: [],
        author: null,
        created_at: '',
        moderation_status: 'published',
      })
    );
    await updatePost('5', { body: [] }, 'key-edit');
    expect(headersOf(fetchMock.mock.calls[0])['Idempotency-Key']).toBe('key-edit');
  });

  it('sendMessage and sendConversationMessage send the given key', async () => {
    fetchMock.mockResolvedValueOnce(json(201, { id: 1 }));
    fetchMock.mockResolvedValueOnce(json(201, { id: 2 }));
    await sendMessage('ada', 'hi', 'key-dm');
    await sendConversationMessage(12, 'hi all', 'key-group');
    expect(headersOf(fetchMock.mock.calls[0])['Idempotency-Key']).toBe('key-dm');
    expect(headersOf(fetchMock.mock.calls[1])['Idempotency-Key']).toBe('key-group');
  });

  it('sends no Idempotency-Key header when none is given', async () => {
    fetchMock.mockResolvedValueOnce(json(201, { id: 3, status: 'published' }));
    await createPost({ thread: 12, body: [] });
    expect(headersOf(fetchMock.mock.calls[0])).not.toHaveProperty('Idempotency-Key');
  });
});

describe('stale CSRF token refresh (F143)', () => {
  it('createPost: a CSRF 403 refetches the token and retries once with the same key', async () => {
    fetchMock
      .mockResolvedValueOnce(csrfFailed())
      .mockResolvedValueOnce(json(200, { csrfToken: 'fresh-token' }))
      .mockResolvedValueOnce(json(201, { id: 3, status: 'published' }));

    await expect(createPost({ thread: 12, body: [] }, 'key-reply')).resolves.toEqual({
      id: '3',
      status: 'published',
    });

    const writes = writeCalls();
    expect(writes).toHaveLength(2);
    expect(headersOf(writes[0])['X-CSRFToken']).toBe('stale-token');
    expect(headersOf(writes[1])['X-CSRFToken']).toBe('fresh-token');
    expect(headersOf(writes[1])['Idempotency-Key']).toBe('key-reply');
    expect(fetchMock.mock.calls.some((c) => c[0] === CSRF_URL)).toBe(true);
  });

  it('sendMessage: a CSRF 403 is retried, not surfaced as a blocked 403', async () => {
    fetchMock
      .mockResolvedValueOnce(csrfFailed())
      .mockResolvedValueOnce(json(200, { csrfToken: 'fresh-token' }))
      .mockResolvedValueOnce(json(201, { id: 31, body: 'hi' }));

    await expect(sendMessage('ada', 'hi', 'key-dm')).resolves.toMatchObject({ id: 31 });
    const writes = writeCalls();
    expect(writes).toHaveLength(2);
    expect(writes[1][0]).toBe(`${BASE}/users/ada/messages/`);
    expect(headersOf(writes[1])['X-CSRFToken']).toBe('fresh-token');
    expect(headersOf(writes[1])['Idempotency-Key']).toBe('key-dm');
  });

  it('uploadPostImage (hand-written fetch) retries a CSRF 403 too', async () => {
    fetchMock
      .mockResolvedValueOnce(csrfFailed())
      .mockResolvedValueOnce(json(200, { csrfToken: 'fresh-token' }))
      .mockResolvedValueOnce(
        json(201, { id: 4, url: '/i.webp', alt: '', decorative: true, width: 1, height: 1 })
      );

    const file = new File(['x'], 'a.png', { type: 'image/png' });
    await expect(uploadPostImage(file, '', 'key-img')).resolves.toMatchObject({ id: 4 });
    const writes = writeCalls();
    expect(writes).toHaveLength(2);
    expect(headersOf(writes[1])['X-CSRFToken']).toBe('fresh-token');
    expect(headersOf(writes[1])['Idempotency-Key']).toBe('key-img');
  });

  it('retries exactly once: a second CSRF 403 is thrown, not looped', async () => {
    fetchMock
      .mockResolvedValueOnce(csrfFailed())
      .mockResolvedValueOnce(json(200, { csrfToken: 'fresh-token' }))
      .mockResolvedValueOnce(csrfFailed());

    const err = await sendMessage('ada', 'hi', 'key-dm').catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ForumApiError);
    expect((err as ForumApiError).status).toBe(403);
    expect(writeCalls()).toHaveLength(2);
  });

  it('a non-CSRF 403 (blocked) is not retried', async () => {
    fetchMock.mockResolvedValueOnce(blocked());

    const err = await sendMessage('ada', 'hi', 'key-dm').catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ForumApiError);
    expect((err as ForumApiError).status).toBe(403);
    expect((err as ForumApiError).message).toBe('You cannot message this user.');
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
