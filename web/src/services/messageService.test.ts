import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  fetchConversations,
  fetchUnreadConversationCount,
  fetchConversationWith,
  fetchMessages,
  sendMessage,
  reportMessage,
  MESSAGE_MAX_LENGTH,
} from './messageService';
import { ForumApiError } from './forumService';
import { clearCsrfToken } from '../utils/csrf';

const BASE = 'http://localhost:8000/api/v1/forum';

const conversation = {
  id: 7,
  other_participant: { username: 'ada', display_name: 'Ada', avatar: null, trust_level: 2 },
  created_at: '2026-09-01T00:00:00Z',
  last_message_at: '2026-09-02T00:00:00Z',
  unread_count: 1,
  last_message: { body: 'hi', is_mine: false, created_at: '2026-09-02T00:00:00Z' },
};

const message = {
  id: 31,
  conversation_id: 7,
  sender: { username: 'ada', display_name: 'Ada', avatar: null, trust_level: 2 },
  body: 'hello there',
  created_at: '2026-09-02T00:00:00Z',
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

function okJson(body: unknown) {
  return { ok: true, status: 200, json: async () => body };
}

function failJson(status: number, body: unknown) {
  return { ok: false, status, json: async () => body };
}

describe('messageService (forum direct messages, todo 339)', () => {
  it('exposes the backend body cap', () => {
    expect(MESSAGE_MAX_LENGTH).toBe(4000);
  });

  it('fetchConversations GETs /conversations/ and returns the cursor page verbatim', async () => {
    fetchMock.mockResolvedValueOnce(
      okJson({ results: [conversation], next: null, previous: null })
    );
    const page = await fetchConversations();
    expect(fetchMock.mock.calls[0][0]).toBe(`${BASE}/conversations/`);
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ credentials: 'include' });
    expect(page.results[0]).toEqual(conversation);
    expect(page.next).toBeNull();
  });

  it('fetchConversations fetches a cursor URL verbatim, never re-prefixed', async () => {
    const cursor = `${BASE}/conversations/?cursor=abc`;
    fetchMock.mockResolvedValueOnce(okJson({ results: [], next: null, previous: null }));
    await fetchConversations(cursor);
    expect(fetchMock.mock.calls[0][0]).toBe(cursor);
  });

  it('fetchUnreadConversationCount returns the bare count', async () => {
    fetchMock.mockResolvedValueOnce(okJson({ count: 3 }));
    await expect(fetchUnreadConversationCount()).resolves.toBe(3);
    expect(fetchMock.mock.calls[0][0]).toBe(`${BASE}/conversations/unread-count/`);
  });

  it('fetchUnreadConversationCount surfaces a 401 as a status-carrying error', async () => {
    fetchMock.mockResolvedValueOnce(
      failJson(401, { message: 'Authentication credentials were not provided.' })
    );
    await expect(fetchUnreadConversationCount()).rejects.toMatchObject({
      status: 401,
      message: 'Authentication credentials were not provided.',
    });
  });

  it('fetchConversationWith encodes the username and returns the row', async () => {
    fetchMock.mockResolvedValueOnce(okJson(conversation));
    const row = await fetchConversationWith('ada lovelace');
    expect(fetchMock.mock.calls[0][0]).toBe(`${BASE}/conversations/with/ada%20lovelace/`);
    expect(row).toEqual(conversation);
  });

  it('fetchConversationWith resolves null on 404 (no thread yet / unknown / blocked)', async () => {
    fetchMock.mockResolvedValueOnce(failJson(404, { message: 'Not found.' }));
    await expect(fetchConversationWith('ghost')).resolves.toBeNull();
  });

  it('fetchConversationWith rethrows every non-404 failure with its status', async () => {
    fetchMock.mockResolvedValueOnce(failJson(500, { message: 'Server error' }));
    const err = await fetchConversationWith('ada').catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ForumApiError);
    expect((err as ForumApiError).status).toBe(500);
  });

  it('fetchMessages GETs the newest page, or a cursor URL verbatim', async () => {
    fetchMock.mockResolvedValueOnce(okJson({ results: [message], next: 'x', previous: null }));
    const page = await fetchMessages(7);
    expect(fetchMock.mock.calls[0][0]).toBe(`${BASE}/conversations/7/messages/`);
    expect(page.results[0]).toEqual(message);

    const cursor = `${BASE}/conversations/7/messages/?cursor=older`;
    fetchMock.mockResolvedValueOnce(okJson({ results: [], next: null, previous: null }));
    await fetchMessages(7, cursor);
    expect(fetchMock.mock.calls[1][0]).toBe(cursor);
  });

  it('sendMessage POSTs {body} to /users/{username}/messages/ with CSRF and returns the message', async () => {
    fetchMock.mockResolvedValueOnce({ ok: true, status: 201, json: async () => message });
    const sent = await sendMessage('ada', 'hello there');
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${BASE}/users/ada/messages/`);
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body)).toEqual({ body: 'hello there' });
    expect(init.headers['X-CSRFToken']).toBe('test-csrf-token');
    expect(sent).toEqual(message);
  });

  it('sendMessage throws a 403 ForumApiError carrying the backend message when blocked', async () => {
    fetchMock.mockResolvedValueOnce(failJson(403, { message: 'You cannot message this user.' }));
    const err = await sendMessage('ada', 'hi').catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ForumApiError);
    expect(err).toMatchObject({ status: 403, message: 'You cannot message this user.' });
  });

  it('sendMessage throws a 400 ForumApiError with the flattened spam/empty reason', async () => {
    fetchMock.mockResolvedValueOnce(failJson(400, { message: 'This message looks like spam.' }));
    await expect(sendMessage('ada', 'BUY NOW')).rejects.toMatchObject({
      status: 400,
      message: 'This message looks like spam.',
    });
  });

  it('reportMessage POSTs {reason, detail} to /messages/{id}/report/', async () => {
    fetchMock.mockResolvedValueOnce(okJson({ reported: true }));
    await reportMessage(31, 'abuse', 'rude');
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${BASE}/messages/31/report/`);
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body)).toEqual({ reason: 'abuse', detail: 'rude' });
  });

  it('reportMessage sends an empty detail when none is given', async () => {
    fetchMock.mockResolvedValueOnce(okJson({ reported: true }));
    await reportMessage(31, 'spam');
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ reason: 'spam', detail: '' });
  });
});
