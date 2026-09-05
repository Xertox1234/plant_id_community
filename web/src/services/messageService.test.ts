import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  fetchConversations,
  fetchUnreadConversationCount,
  fetchConversationWith,
  fetchConversation,
  fetchMessages,
  sendMessage,
  sendConversationMessage,
  createGroupConversation,
  addParticipant,
  removeParticipant,
  reportMessage,
  MESSAGE_MAX_LENGTH,
  GROUP_MAX_OTHERS,
  GROUP_MAX_PARTICIPANTS,
  GROUP_MIN_OTHERS,
  GROUP_TITLE_MAX_LENGTH,
} from './messageService';
import { ForumApiError } from './forumService';
import { clearCsrfToken } from '../utils/csrf';

const BASE = 'http://localhost:8000/api/v1/forum';

const ada = { username: 'ada', display_name: 'Ada', avatar: null, trust_level: 2 };
const me = { username: 'me', display_name: 'Me', avatar: null, trust_level: 1 };
const grace = { username: 'grace', display_name: 'Grace', avatar: null, trust_level: 1 };

const conversation = {
  id: 7,
  kind: 'direct',
  title: '',
  other_participant: ada,
  participants: [me, ada],
  participant_count: 2,
  created_by: null,
  can_manage: false,
  created_at: '2026-09-01T00:00:00Z',
  last_message_at: '2026-09-02T00:00:00Z',
  unread_count: 1,
  last_message: { body: 'hi', is_mine: false, sender: ada, created_at: '2026-09-02T00:00:00Z' },
};

const group = {
  id: 12,
  kind: 'group',
  title: 'Seed swap committee',
  other_participant: null,
  participants: [me, ada, grace],
  participant_count: 3,
  created_by: me,
  can_manage: true,
  created_at: '2026-09-01T00:00:00Z',
  last_message_at: '2026-09-02T00:00:00Z',
  unread_count: 0,
  last_message: {
    body: 'hello all',
    is_mine: true,
    sender: me,
    created_at: '2026-09-02T00:00:00Z',
  },
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

describe('messageService groups (todo 350)', () => {
  it('exposes the group limits the backend enforces', () => {
    expect(GROUP_TITLE_MAX_LENGTH).toBe(80);
    expect(GROUP_MAX_PARTICIPANTS).toBe(8);
    expect(GROUP_MIN_OTHERS).toBe(2);
    expect(GROUP_MAX_OTHERS).toBe(7);
  });

  it('createGroupConversation POSTs exactly {title, usernames, body} to /conversations/ with CSRF and returns the row', async () => {
    fetchMock.mockResolvedValueOnce({ ok: true, status: 201, json: async () => group });
    const row = await createGroupConversation({
      title: 'Seed swap committee',
      usernames: ['ada', 'grace'],
      body: 'hello all',
    });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${BASE}/conversations/`);
    expect(init.method).toBe('POST');
    expect(init.credentials).toBe('include');
    expect(JSON.parse(init.body)).toEqual({
      title: 'Seed swap committee',
      usernames: ['ada', 'grace'],
      body: 'hello all',
    });
    expect(init.headers['X-CSRFToken']).toBe('test-csrf-token');
    expect(row).toEqual(group);
  });

  it('createGroupConversation surfaces the generic 400 as a status-carrying error with no retryAfter', async () => {
    fetchMock.mockResolvedValueOnce(
      failJson(400, { message: 'One of the members cannot be added.' })
    );
    const err = await createGroupConversation({
      title: 't',
      usernames: ['x', 'y'],
      body: 'b',
    }).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ForumApiError);
    expect(err).toMatchObject({
      status: 400,
      message: 'One of the members cannot be added.',
      retryAfter: null,
    });
  });

  it('a 429 carries the integer Retry-After seconds', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 429,
      headers: { get: (name: string) => (name === 'Retry-After' ? '900' : null) },
      json: async () => ({ message: 'Request was throttled.' }),
    });
    const err = await createGroupConversation({
      title: 't',
      usernames: ['x', 'y'],
      body: 'b',
    }).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ForumApiError);
    expect(err).toMatchObject({ status: 429, message: 'Request was throttled.', retryAfter: 900 });
  });

  it('a 429 without a delta-seconds Retry-After carries null (absent header, HTTP-date form, no Headers object)', async () => {
    fetchMock
      .mockResolvedValueOnce({
        ok: false,
        status: 429,
        headers: { get: () => null },
        json: async () => ({ message: 'throttled' }),
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 429,
        headers: { get: () => 'Wed, 21 Oct 2026 07:28:00 GMT' },
        json: async () => ({ message: 'throttled' }),
      })
      .mockResolvedValueOnce(failJson(429, { message: 'throttled' }));
    for (let i = 0; i < 3; i += 1) {
      const err = await sendConversationMessage(12, 'x').catch((e: unknown) => e);
      expect(err).toMatchObject({ status: 429, retryAfter: null });
    }
  });

  it('only a 429 reads Retry-After — a 400 with the header still carries null', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 400,
      headers: { get: () => '5' },
      json: async () => ({ message: 'bad' }),
    });
    const err = await sendConversationMessage(12, 'x').catch((e: unknown) => e);
    expect(err).toMatchObject({ status: 400, retryAfter: null });
  });

  it('sendConversationMessage POSTs {body} to /conversations/{id}/messages/ and returns the message', async () => {
    const sentMessage = { ...message, id: 40, conversation_id: 12, sender: me, body: 'hi all' };
    fetchMock.mockResolvedValueOnce({ ok: true, status: 201, json: async () => sentMessage });
    const sent = await sendConversationMessage(12, 'hi all');
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${BASE}/conversations/12/messages/`);
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body)).toEqual({ body: 'hi all' });
    expect(init.headers['X-CSRFToken']).toBe('test-csrf-token');
    expect(sent).toEqual(sentMessage);
  });

  it('sendConversationMessage throws a 403 ForumApiError with the backend line for a block-paired group', async () => {
    fetchMock.mockResolvedValueOnce(failJson(403, { message: 'You cannot message this group.' }));
    await expect(sendConversationMessage(12, 'hi')).rejects.toMatchObject({
      status: 403,
      message: 'You cannot message this group.',
    });
  });

  it('addParticipant POSTs {username} to /conversations/{id}/participants/ and returns the row', async () => {
    fetchMock.mockResolvedValueOnce(okJson(group));
    const row = await addParticipant(12, 'grace');
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${BASE}/conversations/12/participants/`);
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body)).toEqual({ username: 'grace' });
    expect(row).toEqual(group);
  });

  it('removeParticipant DELETEs /conversations/{id}/participants/{username}/ (encoded) and resolves on 204', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 204,
      json: async () => {
        throw new Error('204 has no body');
      },
    });
    await expect(removeParticipant(12, 'ada lovelace')).resolves.toBeUndefined();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${BASE}/conversations/12/participants/ada%20lovelace/`);
    expect(init.method).toBe('DELETE');
    expect(init.headers['X-CSRFToken']).toBe('test-csrf-token');
  });

  it('removeParticipant surfaces the creator-cannot-leave 400 with its message', async () => {
    fetchMock.mockResolvedValueOnce(
      failJson(400, { message: 'Transfer or close the group first.' })
    );
    await expect(removeParticipant(12, 'me')).rejects.toMatchObject({
      status: 400,
      message: 'Transfer or close the group first.',
    });
  });

  it('fetchConversation GETs exactly /conversations/{id}/ — one request, never an inbox walk — and returns the row', async () => {
    fetchMock.mockResolvedValueOnce(okJson(group));
    const row = await fetchConversation(12);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe(`${BASE}/conversations/12/`);
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ credentials: 'include' });
    expect(row).toEqual(group);
  });

  it('fetchConversation resolves null on 404 (non-participant, removed member, blocked direct pair)', async () => {
    fetchMock.mockResolvedValueOnce(failJson(404, { message: 'Not found.' }));
    await expect(fetchConversation(999)).resolves.toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('fetchConversation rethrows every non-404 failure with its status', async () => {
    fetchMock.mockResolvedValueOnce(failJson(500, { message: 'Server error' }));
    const err = await fetchConversation(12).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ForumApiError);
    expect((err as ForumApiError).status).toBe(500);
  });

  it('membership 400s arrive as the bare sentence in the envelope message — no field prefix', async () => {
    fetchMock
      .mockResolvedValueOnce(failJson(400, { message: 'A group may have at most 8 members.' }))
      .mockResolvedValueOnce(
        failJson(400, { message: 'A group needs at least two other members.' })
      );
    await expect(addParticipant(12, 'u9')).rejects.toMatchObject({
      status: 400,
      message: 'A group may have at most 8 members.',
    });
    await expect(
      createGroupConversation({ title: 't', usernames: ['x'], body: 'b' })
    ).rejects.toMatchObject({
      status: 400,
      message: 'A group needs at least two other members.',
    });
  });
});
