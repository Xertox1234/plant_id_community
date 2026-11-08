import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  AccountDeletionError,
  confirmAccountDeletion,
  requestAccountDeletion,
} from './accountDeletionService';

function reply(status: number, body: unknown) {
  return vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  });
}

describe('accountDeletionService', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', reply(200, { status: 'sent' }));
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('requestAccountDeletion posts the email', async () => {
    await requestAccountDeletion('a@b.com');
    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect(String(url)).toMatch(/\/api\/v1\/auth\/account\/delete\/request\/$/);
    expect(init?.method).toBe('POST');
    expect(JSON.parse(String(init?.body))).toEqual({ email: 'a@b.com' });
  });

  it('requestAccountDeletion maps 429 to a rate-limit error', async () => {
    vi.stubGlobal('fetch', reply(429, {}));
    await expect(requestAccountDeletion('a@b.com')).rejects.toMatchObject({ code: 'rate_limited' });
  });

  it('requestAccountDeletion maps other failures to a generic error', async () => {
    vi.stubGlobal('fetch', reply(500, {}));
    await expect(requestAccountDeletion('a@b.com')).rejects.toMatchObject({ code: 'error' });
  });

  it('confirmAccountDeletion posts the token with credentials and returns scheduled', async () => {
    vi.stubGlobal('fetch', reply(202, { status: 'scheduled' }));
    await expect(confirmAccountDeletion('tok')).resolves.toBe('scheduled');
    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect(String(url)).toMatch(/\/api\/v1\/auth\/account\/delete\/confirm\/$/);
    expect(JSON.parse(String(init?.body))).toEqual({ token: 'tok' });
    expect(init?.credentials).toBe('include');
  });

  it.each(['link_invalid', 'contact_support'])('confirm throws a typed %s error', async (code) => {
    vi.stubGlobal(
      'fetch',
      reply(code === 'link_invalid' ? 400 : 409, { code, error: 'Server text' })
    );
    const err = await confirmAccountDeletion('tok').catch((e: unknown) => e);
    expect(err).toBeInstanceOf(AccountDeletionError);
    expect(err).toMatchObject({ code, message: 'Server text' });
  });

  it('confirm maps a network failure to a generic error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('down')));
    await expect(confirmAccountDeletion('tok')).rejects.toMatchObject({ code: 'error' });
  });
});
