import { describe, it, expect, vi, beforeEach } from 'vitest';
import { UnsubscribeError, checkUnsubscribe, confirmUnsubscribe } from './unsubscribeService';

function jsonResponse(body: unknown, status = 200) {
  return { ok: status < 400, status, json: () => Promise.resolve(body) } as Response;
}

const STATE = { list: 'forum_reply', label: 'Replies', subscribed: true };

async function reasonOf(promise: Promise<unknown>) {
  const err = await promise.then(
    () => null,
    (e: unknown) => e
  );
  expect(err).toBeInstanceOf(UnsubscribeError);
  return (err as UnsubscribeError).reason;
}

describe('unsubscribeService', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    global.fetch = fetchMock as unknown as typeof fetch;
  });

  it('checks a link by POSTing the token, without cookies', async () => {
    fetchMock.mockResolvedValue(jsonResponse(STATE));

    await expect(checkUnsubscribe('tok')).resolves.toEqual(STATE);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/api\/v1\/auth\/unsubscribe\/check\/$/);
    expect(init.method).toBe('POST');
    // The token is the credential: a signed-in session must not ride along.
    expect(init.credentials).toBe('omit');
    expect(JSON.parse(init.body)).toEqual({ token: 'tok' });
  });

  it('unsubscribes at /api/v1/auth/unsubscribe/', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ ...STATE, subscribed: false }));

    await expect(confirmUnsubscribe('tok')).resolves.toMatchObject({ subscribed: false });
    expect(fetchMock.mock.calls[0][0]).toMatch(/\/api\/v1\/auth\/unsubscribe\/$/);
  });

  it('maps the backend codes for a forged and an expired link', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ code: 'invalid', message: 'x' }, 400));
    expect(await reasonOf(checkUnsubscribe('tok'))).toBe('invalid');
    fetchMock.mockResolvedValueOnce(jsonResponse({ code: 'expired', message: 'x' }, 400));
    expect(await reasonOf(checkUnsubscribe('tok'))).toBe('expired');
  });

  it('treats a network failure, a 429 and a malformed body as a generic error', async () => {
    fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'));
    expect(await reasonOf(checkUnsubscribe('tok'))).toBe('error');
    fetchMock.mockResolvedValueOnce(jsonResponse({ code: 'rate_limit_exceeded' }, 429));
    expect(await reasonOf(checkUnsubscribe('tok'))).toBe('error');
    fetchMock.mockResolvedValueOnce(jsonResponse({ unexpected: true }));
    expect(await reasonOf(confirmUnsubscribe('tok'))).toBe('error');
  });
});
