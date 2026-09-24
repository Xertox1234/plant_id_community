import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { fetchNotifications, fetchUnreadCount, markNotificationsRead } from './notificationService';
import apiClient from '../utils/httpClient';
import { clearCsrfToken, getCsrfToken } from '../utils/csrf';
import {
  CSRF_FAILED_BODY,
  captureXhrHeaders,
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

describe('notificationService', () => {
  let adapter: AdapterMock;

  beforeEach(() => {
    vi.mocked(getCsrfToken).mockResolvedValue('csrf-123');
    adapter = installAdapter();
  });

  afterEach(() => {
    restoreAdapter();
  });

  it('reads the unread count from /api/v1/forum/notifications/unread-count/', async () => {
    adapter.mockImplementation(async (config) => ok(config, { count: 4 }));

    await expect(fetchUnreadCount()).resolves.toBe(4);
    const config = adapter.mock.calls[0][0];
    expect(config.method).toBe('get');
    expect(fullUrl(config)).toBe(
      `${apiClient.defaults.baseURL}/api/v1/forum/notifications/unread-count/`
    );
    expect(config.withCredentials).toBe(true);
  });

  it('lists the first page from /api/v1/forum/notifications/', async () => {
    const page = { next: null, previous: null, results: [] };
    adapter.mockImplementation(async (config) => ok(config, page));

    await expect(fetchNotifications()).resolves.toEqual(page);
    expect(fullUrl(adapter.mock.calls[0][0])).toBe(
      `${apiClient.defaults.baseURL}/api/v1/forum/notifications/`
    );
  });

  it('fetches an absolute DRF cursor URL verbatim, never re-prefixed', async () => {
    const cursor = 'https://api.example.test/api/v1/forum/notifications/?cursor=cD0yMDI2';
    adapter.mockImplementation(async (config) => ok(config, { next: null, results: [] }));

    await fetchNotifications(cursor);
    expect(fullUrl(adapter.mock.calls[0][0])).toBe(cursor);
  });

  it('POSTs specific ids to mark-read with the CSRF token, returning the updated count', async () => {
    adapter.mockImplementation(async (config) => ok(config, { updated: 2 }));

    await expect(markNotificationsRead([7, 9])).resolves.toBe(2);
    const config = adapter.mock.calls[0][0];
    expect(config.method).toBe('post');
    expect(fullUrl(config)).toMatch(/\/api\/v1\/forum\/notifications\/mark-read\/$/);
    expect(config.headers.get('X-CSRFToken')).toBe('csrf-123');
    expect(JSON.parse(config.data)).toEqual({ ids: [7, 9] });
  });

  it('POSTs an empty object to mark ALL read when no ids are given', async () => {
    adapter.mockImplementation(async (config) => ok(config, { updated: 5 }));

    await expect(markNotificationsRead()).resolves.toBe(5);
    expect(JSON.parse(adapter.mock.calls[0][0].data)).toEqual({});
  });

  it('resolves undefined for a 204', async () => {
    adapter.mockImplementation(async (config) => ok(config, '', 204));

    await expect(fetchNotifications()).resolves.toBeUndefined();
  });

  it.each([
    [
      'the flattened message',
      { message: 'Authentication credentials were not provided.' },
      'Authentication credentials were not provided.',
    ],
    ['a bare DRF detail', { detail: 'Not found.' }, 'Not found.'],
    ['the status, for a JSON body with neither', {}, 'HTTP 500'],
    ['"Request failed", for a non-JSON body', '<html>oops</html>', 'Request failed'],
  ])('rejects with %s', async (_label, body, expected) => {
    adapter.mockImplementation(async (config) => {
      throw httpError(config, 500, body);
    });

    await expect(fetchUnreadCount()).rejects.toThrow(expected);
  });

  it('refreshes a stale CSRF token and retries mark-read once (todo 407)', async () => {
    vi.mocked(getCsrfToken).mockResolvedValueOnce('stale').mockResolvedValue('fresh');
    const sentTokens: (string | undefined)[] = [];
    adapter.mockImplementation(async (config) => {
      sentTokens.push(config.headers.get('X-CSRFToken') as string | undefined);
      if (sentTokens.length === 1) throw httpError(config, 403, CSRF_FAILED_BODY);
      return ok(config, { updated: 1 });
    });

    await expect(markNotificationsRead([3])).resolves.toBe(1);
    expect(sentTokens).toEqual(['stale', 'fresh']);
    expect(clearCsrfToken).toHaveBeenCalledTimes(1);
    expect(JSON.parse(adapter.mock.calls[1][0].data)).toEqual({ ids: [3] });
  });

  it('does not retry a 403 that is not a CSRF failure', async () => {
    adapter.mockImplementation(async (config) => {
      throw httpError(config, 403, {
        message: 'You do not have permission to perform this action.',
      });
    });

    await expect(markNotificationsRead()).rejects.toThrow(
      'You do not have permission to perform this action.'
    );
    expect(adapter).toHaveBeenCalledTimes(1);
    expect(clearCsrfToken).not.toHaveBeenCalled();
  });

  it('sends a bodyless GET without Content-Type or a CSRF header', async () => {
    restoreAdapter();
    const sentHeaders = captureXhrHeaders();

    void fetchUnreadCount();

    await vi.waitFor(() => expect(sentHeaders()).toContain('accept'));
    expect(sentHeaders()).not.toContain('content-type');
    expect(sentHeaders()).not.toContain('x-csrftoken');
  });

  // PR #817 review: axios resolves a non-JSON body as a string, where fetch's
  // response.json() rejected. The service must keep rejecting.
  it('a non-JSON 200 body (CDN challenge page) rejects instead of resolving undefined', async () => {
    adapter.mockImplementation(async (config) => ok(config, '<html>challenge</html>'));

    await expect(fetchUnreadCount()).rejects.toThrow();
  });
});
