import { describe, it, expect, vi, beforeEach } from 'vitest';
import { fetchDashboardStats, fetchProfile, updateProfile } from './profileService';
import { getCsrfToken } from '../utils/csrf';

vi.mock('../utils/csrf', () => ({ getCsrfToken: vi.fn() }));

function jsonResponse(body: unknown, status = 200) {
  return { ok: status < 400, status, json: () => Promise.resolve(body) } as Response;
}

describe('profileService', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.mocked(getCsrfToken).mockResolvedValue('csrf-123');
    fetchMock = vi.fn();
    global.fetch = fetchMock as unknown as typeof fetch;
  });

  it('reads the profile from /api/v1/auth/user/ with cookies', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ id: 1, username: 'ada' }));

    await expect(fetchProfile()).resolves.toMatchObject({ username: 'ada' });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/api\/v1\/auth\/user\/$/);
    expect(init.credentials).toBe('include');
  });

  it('PATCHes changes to /api/v1/auth/user/update/ with the CSRF token, returning the user', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ message: 'Profile updated successfully', user: { id: 1, bio: 'Ferns' } })
    );

    await expect(updateProfile({ bio: 'Ferns' })).resolves.toEqual({ id: 1, bio: 'Ferns' });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/api\/v1\/auth\/user\/update\/$/);
    expect(init.method).toBe('PATCH');
    expect(init.headers['X-CSRFToken']).toBe('csrf-123');
    expect(JSON.parse(init.body)).toEqual({ bio: 'Ferns' });
  });

  it('turns a DRF field-error map into one readable message', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ website: ['Enter a valid URL.'] }, 400));

    await expect(updateProfile({ website: 'nope' })).rejects.toThrow('website: Enter a valid URL.');
  });

  it('prefers a flattened {message} error body', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ message: 'Invalid first name' }, 400));

    await expect(updateProfile({ first_name: 'x' })).rejects.toThrow('Invalid first name');
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
      fetchMock.mockResolvedValue(
        jsonResponse({ forum_stats: forumStats, recent_activity: [topicItem] })
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
      const [url, init] = fetchMock.mock.calls[0];
      expect(url).toMatch(/\/api\/v1\/auth\/me\/dashboard-stats\/$/);
      expect(init.credentials).toBe('include');
    });

    it('never passes on the removed plant fields or non-forum activity', async () => {
      // An older server still sends the plant block. None of it may reach the page.
      fetchMock.mockResolvedValue(
        jsonResponse({
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
      fetchMock.mockResolvedValue(jsonResponse({ recent_activity: [] }));

      await expect(fetchDashboardStats()).rejects.toThrow(/unexpected/i);
    });

    it('surfaces the server error message', async () => {
      fetchMock.mockResolvedValue(
        jsonResponse({ detail: 'Authentication credentials were not provided.' }, 401)
      );

      await expect(fetchDashboardStats()).rejects.toThrow(
        'Authentication credentials were not provided.'
      );
    });
  });
});
