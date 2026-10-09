import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  NewsletterLinkError,
  NewsletterSignupError,
  confirmNewsletter,
  subscribeToNewsletter,
  unsubscribeNewsletter,
} from './newsletterService';

function jsonResponse(body: unknown, status = 200) {
  return { ok: status < 400, status, json: () => Promise.resolve(body) } as Response;
}

async function errorOf(promise: Promise<unknown>) {
  return promise.then(
    () => null,
    (e: unknown) => e
  );
}

describe('newsletterService', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    global.fetch = fetchMock as unknown as typeof fetch;
  });

  it('signs up with a JSON POST and no cookies', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: 'Check your inbox' }, 202));

    await expect(subscribeToNewsletter('a@example.com')).resolves.toBeUndefined();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/api\/v1\/blog\/newsletter\/$/);
    expect(init.method).toBe('POST');
    expect(init.credentials).toBe('omit');
    // The backend parses JSON only (another site's form cannot sign people up).
    expect(init.headers['Content-Type']).toBe('application/json');
    expect(JSON.parse(init.body)).toEqual({ email: 'a@example.com' });
  });

  it.each([
    [400, 'invalid_email'],
    [429, 'rate_limited'],
    [500, 'error'],
  ])('maps a %i signup answer to %s', async (status, reason) => {
    fetchMock.mockResolvedValue(jsonResponse({}, status));
    const err = await errorOf(subscribeToNewsletter('a@example.com'));
    expect(err).toBeInstanceOf(NewsletterSignupError);
    expect((err as NewsletterSignupError).reason).toBe(reason);
  });

  it('reports a network failure as an error', async () => {
    fetchMock.mockRejectedValue(new TypeError('offline'));
    const err = await errorOf(subscribeToNewsletter('a@example.com'));
    expect((err as NewsletterSignupError).reason).toBe('error');
  });

  it('confirms and unsubscribes by POSTing the token, without cookies', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ subscribed: true }));
    await expect(confirmNewsletter('tok')).resolves.toBe(true);
    fetchMock.mockResolvedValueOnce(jsonResponse({ subscribed: false }));
    await expect(unsubscribeNewsletter('tok')).resolves.toBe(false);

    const [[confirmUrl, confirmInit], [unsubUrl, unsubInit]] = fetchMock.mock.calls;
    expect(confirmUrl).toMatch(/\/api\/v1\/blog\/newsletter\/confirm\/$/);
    expect(unsubUrl).toMatch(/\/api\/v1\/blog\/newsletter\/unsubscribe\/$/);
    for (const init of [confirmInit, unsubInit]) {
      expect(init.method).toBe('POST');
      expect(init.credentials).toBe('omit');
      expect(JSON.parse(init.body)).toEqual({ token: 'tok' });
    }
  });

  it.each([
    [jsonResponse({ code: 'invalid', message: 'x' }, 400), 'invalid'],
    [jsonResponse({ code: 'expired', message: 'x' }, 400), 'expired'],
    [jsonResponse({}, 429), 'rate_limited'],
    [jsonResponse({ detail: 'boom' }, 500), 'error'],
    // A 200 without the expected shape is not a success.
    [jsonResponse({ unexpected: true }), 'error'],
  ])('maps a failed link answer to its reason (%#)', async (response, reason) => {
    fetchMock.mockResolvedValue(response);
    const err = await errorOf(confirmNewsletter('tok'));
    expect(err).toBeInstanceOf(NewsletterLinkError);
    expect((err as NewsletterLinkError).reason).toBe(reason);
  });
});
