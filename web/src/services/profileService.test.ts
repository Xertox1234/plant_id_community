import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { fetchDashboardStats, fetchProfile, updateProfile } from './profileService';
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

describe('profileService', () => {
  let adapter: AdapterMock;

  beforeEach(() => {
    vi.mocked(getCsrfToken).mockResolvedValue('csrf-123');
    adapter = installAdapter();
  });

  afterEach(() => {
    restoreAdapter();
  });

  it('reads the profile from /api/v1/auth/user/ with cookies', async () => {
    adapter.mockImplementation(async (config) => ok(config, { id: 1, username: 'ada' }));

    await expect(fetchProfile()).resolves.toMatchObject({ username: 'ada' });
    const config = adapter.mock.calls[0][0];
    expect(config.method).toBe('get');
    expect(fullUrl(config)).toMatch(/\/api\/v1\/auth\/user\/$/);
    expect(config.withCredentials).toBe(true);
  });

  it('PATCHes changes to /api/v1/auth/user/update/ with the CSRF token, returning the user', async () => {
    adapter.mockImplementation(async (config) =>
      ok(config, { message: 'Profile updated successfully', user: { id: 1, bio: 'Ferns' } })
    );

    await expect(updateProfile({ bio: 'Ferns' })).resolves.toEqual({ id: 1, bio: 'Ferns' });
    const config = adapter.mock.calls[0][0];
    expect(fullUrl(config)).toMatch(/\/api\/v1\/auth\/user\/update\/$/);
    expect(config.method).toBe('patch');
    expect(config.headers.get('X-CSRFToken')).toBe('csrf-123');
    expect(JSON.parse(config.data)).toEqual({ bio: 'Ferns' });
  });

  it('turns a DRF field-error map into one readable message', async () => {
    adapter.mockImplementation(async (config) => {
      throw httpError(config, 400, { website: ['Enter a valid URL.'] });
    });

    await expect(updateProfile({ website: 'nope' })).rejects.toThrow('website: Enter a valid URL.');
  });

  it('prefers a flattened {message} error body', async () => {
    adapter.mockImplementation(async (config) => {
      throw httpError(config, 400, { message: 'Invalid first name' });
    });

    await expect(updateProfile({ first_name: 'x' })).rejects.toThrow('Invalid first name');
  });

  it('falls back to the status when the error body is not JSON', async () => {
    adapter.mockImplementation(async (config) => {
      throw httpError(config, 502, '<html>Bad gateway</html>');
    });

    await expect(fetchProfile()).rejects.toThrow('Request failed (HTTP 502)');
  });

  it('refreshes a stale CSRF token and retries the PATCH once (todo 407)', async () => {
    // The request interceptor reads the token, the 403 handler re-reads it
    // after clearing the cache, and the retry's request interceptor reads it
    // again — that last value is what ships.
    vi.mocked(getCsrfToken).mockResolvedValueOnce('stale').mockResolvedValue('fresh');
    const sentTokens: (string | undefined)[] = [];
    adapter.mockImplementation(async (config) => {
      sentTokens.push(config.headers.get('X-CSRFToken') as string | undefined);
      if (sentTokens.length === 1) throw httpError(config, 403, CSRF_FAILED_BODY);
      return ok(config, { message: 'Profile updated successfully', user: { id: 1, bio: 'Ferns' } });
    });

    await expect(updateProfile({ bio: 'Ferns' })).resolves.toEqual({ id: 1, bio: 'Ferns' });
    expect(sentTokens).toEqual(['stale', 'fresh']);
    expect(clearCsrfToken).toHaveBeenCalledTimes(1);
    expect(JSON.parse(adapter.mock.calls[1][0].data)).toEqual({ bio: 'Ferns' });
  });

  it('retries a CSRF 403 only once, then surfaces the server message', async () => {
    adapter.mockImplementation(async (config) => {
      throw httpError(config, 403, CSRF_FAILED_BODY);
    });

    await expect(updateProfile({ bio: 'Ferns' })).rejects.toThrow(CSRF_FAILED_BODY.message);
    expect(adapter).toHaveBeenCalledTimes(2);
  });

  it('sends a bodyless GET without Content-Type or a CSRF header', async () => {
    restoreAdapter();
    const sentHeaders = captureXhrHeaders();

    void fetchProfile();

    await vi.waitFor(() => expect(sentHeaders()).toContain('accept'));
    expect(sentHeaders()).not.toContain('content-type');
    expect(sentHeaders()).not.toContain('x-csrftoken');
  });

  it('still sends Content-Type: application/json on the PATCH that has a body', async () => {
    restoreAdapter();
    const sentHeaders = captureXhrHeaders();

    void updateProfile({ bio: 'Ferns' });

    await vi.waitFor(() => expect(sentHeaders()).toContain('x-csrftoken'));
    expect(sentHeaders()).toContain('content-type');
  });

  // PR #817 review: axios resolves a non-JSON body as a string, where fetch's
  // response.json() rejected. The service must keep rejecting.
  it('a non-JSON 200 body rejects instead of resolving a string as the profile', async () => {
    adapter.mockImplementation(async (config) => ok(config, '<html>challenge</html>'));

    await expect(fetchProfile()).rejects.toThrow();
  });

  describe('fetchDashboardStats (todo 411)', () => {
    const forumStats = {
      total_topics: 3,
      total_posts: 7,
      topics_this_month: 1,
      posts_this_month: 2,
    };
    const topicItem = {
      type: 'forum_topic',
      title: 'Created topic: Fern help',
      description: 'in General',
      timestamp: '2026-09-20T10:00:00Z',
      url: '/forum/4-general/12-fern-help',
      icon: 'message-circle',
    };

    it('reads /api/v1/auth/me/dashboard-stats/ with cookies', async () => {
      adapter.mockImplementation(async (config) =>
        ok(config, { forum_stats: forumStats, recent_activity: [topicItem] })
      );

      await expect(fetchDashboardStats()).resolves.toEqual({
        forum_stats: forumStats,
        recent_activity: [
          {
            type: 'forum_topic',
            title: 'Created topic: Fern help',
            description: 'in General',
            timestamp: '2026-09-20T10:00:00Z',
            url: '/forum/4-general/12-fern-help',
          },
        ],
      });
      const config = adapter.mock.calls[0][0];
      expect(config.method).toBe('get');
      expect(fullUrl(config)).toMatch(/\/api\/v1\/auth\/me\/dashboard-stats\/$/);
      expect(config.withCredentials).toBe(true);
    });

    it('never passes on the removed plant fields or non-forum activity', async () => {
      // An older server still sends the plant block. None of it may reach the page.
      adapter.mockImplementation(async (config) =>
        ok(config, {
          plant_stats: { total_identified: 5, saved_care_cards: 2 },
          total_activity_score: 99,
          forum_stats: forumStats,
          recent_activity: [
            {
              type: 'plant_identification',
              title: 'Identified plant',
              description: 'Successfully identified a plant species',
              timestamp: '2026-09-21T10:00:00Z',
              url: '/identify/0b8e',
            },
            topicItem,
            { ...topicItem, type: 'forum_post', url: 'https://evil.example/forum/1-x/2-y' },
            { ...topicItem, type: 'badge_award', url: '/forum/4-general/99-badges' },
          ],
        })
      );

      const stats = await fetchDashboardStats();

      expect(Object.keys(stats).sort()).toEqual(['forum_stats', 'recent_activity']);
      expect(stats.recent_activity.map((item) => item.url)).toEqual([
        '/forum/4-general/12-fern-help',
      ]);
    });

    it('rejects a body that is not the stats shape', async () => {
      adapter.mockImplementation(async (config) => ok(config, { recent_activity: [] }));

      await expect(fetchDashboardStats()).rejects.toThrow(/unexpected/i);
    });

    it('surfaces the server error message', async () => {
      adapter.mockImplementation(async (config) => {
        throw httpError(config, 401, { detail: 'Authentication credentials were not provided.' });
      });

      await expect(fetchDashboardStats()).rejects.toThrow(
        'Authentication credentials were not provided.'
      );
    });
  });
});
