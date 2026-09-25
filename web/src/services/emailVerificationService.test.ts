import { describe, it, expect, vi, beforeEach } from 'vitest';
import { VerificationError, confirmEmailVerification } from './emailVerificationService';

function jsonResponse(body: unknown, status = 200) {
  return { ok: status < 400, status, json: () => Promise.resolve(body) } as Response;
}

async function reasonOf(promise: Promise<unknown>) {
  const err = await promise.then(
    () => null,
    (e: unknown) => e
  );
  expect(err).toBeInstanceOf(VerificationError);
  return (err as VerificationError).reason;
}

describe('emailVerificationService', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    global.fetch = fetchMock as unknown as typeof fetch;
  });

  it('confirms by POSTing the key, without cookies', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ verified: true }));

    await expect(confirmEmailVerification('k1')).resolves.toBeUndefined();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/api\/v1\/auth\/verify-email\/$/);
    expect(init.method).toBe('POST');
    // The key is the credential: a signed-in session must not ride along.
    expect(init.credentials).toBe('omit');
    expect(JSON.parse(init.body)).toEqual({ key: 'k1' });
  });

  it('reports a 400 as an invalid link', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ code: 'VERIFICATION_KEY_INVALID' }, 400));

    expect(await reasonOf(confirmEmailVerification('bad'))).toBe('invalid');
  });

  it('reports a server or network failure as retryable', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({}, 503));
    expect(await reasonOf(confirmEmailVerification('k'))).toBe('error');

    fetchMock.mockRejectedValueOnce(new TypeError('offline'));
    expect(await reasonOf(confirmEmailVerification('k'))).toBe('error');
  });
});
