import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { VerificationError, confirmEmailVerification } from './emailVerificationService';
import { getCsrfToken } from '../utils/csrf';
import {
  fullUrl,
  httpError,
  installAdapter,
  ok,
  restoreAdapter,
  type AdapterMock,
} from '../tests/apiClientHarness';

vi.mock('../utils/csrf', () => ({ getCsrfToken: vi.fn(), clearCsrfToken: vi.fn() }));
vi.mock('../utils/logger', () => ({
  logger: { debug: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));

async function reasonOf(promise: Promise<unknown>) {
  const err = await promise.then(
    () => null,
    (e: unknown) => e
  );
  expect(err).toBeInstanceOf(VerificationError);
  return (err as VerificationError).reason;
}

describe('emailVerificationService', () => {
  let adapter: AdapterMock;

  beforeEach(() => {
    vi.mocked(getCsrfToken).mockResolvedValue('csrf-123');
    adapter = installAdapter();
  });

  afterEach(() => {
    restoreAdapter();
  });

  it('confirms WITH the session: the key alone must not be enough', async () => {
    adapter.mockImplementation(async (config) => ok(config, { verified: true }));

    await expect(confirmEmailVerification('k1')).resolves.toBeUndefined();
    const config = adapter.mock.calls[0][0];
    expect(config.method).toBe('post');
    expect(fullUrl(config)).toMatch(/\/api\/v1\/auth\/verify-email\/$/);
    expect(config.withCredentials).toBe(true);
    expect(config.headers.get('X-CSRFToken')).toBe('csrf-123');
    expect(JSON.parse(config.data as string)).toEqual({ key: 'k1' });
  });

  it('reports a 400 as an invalid link', async () => {
    adapter.mockImplementation(async (config) => {
      throw httpError(config, 400, { code: 'VERIFICATION_KEY_INVALID' });
    });

    expect(await reasonOf(confirmEmailVerification('bad'))).toBe('invalid');
  });

  it('reports a missing session as sign-in needed', async () => {
    adapter.mockImplementation(async (config) => {
      throw httpError(config, 401, { detail: 'Authentication credentials were not provided.' });
    });

    expect(await reasonOf(confirmEmailVerification('k'))).toBe('signin');
  });

  it('reports a server failure as retryable', async () => {
    adapter.mockImplementation(async (config) => {
      throw httpError(config, 503, {});
    });

    expect(await reasonOf(confirmEmailVerification('k'))).toBe('error');
  });
});
