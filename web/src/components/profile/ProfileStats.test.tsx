import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ProfileStats from './ProfileStats';
import { getCsrfToken } from '../../utils/csrf';

// The real profileService runs against a mocked fetch, so these tests cover the
// fetch-boundary guard and the render together (todo 411).
vi.mock('../../utils/csrf', () => ({ getCsrfToken: vi.fn() }));

function jsonResponse(body: unknown, status = 200) {
  return { ok: status < 400, status, json: () => Promise.resolve(body) } as Response;
}

const forumStats = {
  total_topics: 3,
  total_posts: 7,
  topics_this_month: 1,
  posts_this_month: 2,
};

const activity = [
  {
    type: 'forum_post',
    title: 'Replied to: Fern help',
    description: 'in General',
    timestamp: '2026-09-21T10:00:00Z',
    url: '/forum/4-general/12-fern-help',
    icon: 'message-square',
  },
  {
    type: 'forum_topic',
    title: 'Created topic: Moss walls',
    description: 'in Projects',
    timestamp: '2026-09-20T10:00:00Z',
    url: '/forum/5-projects/13-moss-walls',
    icon: 'message-circle',
  },
];

function renderStats() {
  return render(
    <MemoryRouter>
      <ProfileStats />
    </MemoryRouter>
  );
}

describe('ProfileStats (todo 411)', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.mocked(getCsrfToken).mockResolvedValue('csrf-123');
    fetchMock = vi.fn();
    global.fetch = fetchMock as unknown as typeof fetch;
  });

  it('shows a loading state, then the forum totals and recent activity', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ forum_stats: forumStats, recent_activity: activity })
    );
    renderStats();

    expect(screen.getByText('Loading your activity…')).toBeInTheDocument();

    expect(await screen.findByText('Topics')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByText('1 in the last 30 days')).toBeInTheDocument();
    expect(screen.getByText('Posts')).toBeInTheDocument();
    expect(screen.getByText('7')).toBeInTheDocument();
    expect(screen.getByText('2 in the last 30 days')).toBeInTheDocument();

    const reply = screen.getByRole('link', { name: 'Replied to: Fern help' });
    expect(reply).toHaveAttribute('href', '/forum/4-general/12-fern-help');
    expect(screen.getByRole('link', { name: 'Created topic: Moss walls' })).toHaveAttribute(
      'href',
      '/forum/5-projects/13-moss-walls'
    );
    expect(screen.queryByText('Loading your activity…')).not.toBeInTheDocument();
  });

  it('shows the error message when the stats cannot load', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: 'Server exploded' }, 500));
    renderStats();

    expect(await screen.findByRole('alert')).toHaveTextContent('Server exploded');
    expect(screen.queryByText('Topics')).not.toBeInTheDocument();
  });

  it('shows an empty state with a way into the forum when there is no activity', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({
        forum_stats: { total_topics: 0, total_posts: 0, topics_this_month: 0, posts_this_month: 0 },
        recent_activity: [],
      })
    );
    renderStats();

    expect(await screen.findByText(/haven’t posted in the forum yet/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Visit the forum' })).toHaveAttribute('href', '/forum');
    expect(screen.queryByText('Topics')).not.toBeInTheDocument();
  });

  it('never renders the removed plant fields an older server may still send', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({
        plant_stats: {
          total_identified: 5,
          total_searches: 9,
          searches_this_week: 4,
          saved_care_cards: 2,
        },
        total_activity_score: 99,
        forum_stats: forumStats,
        recent_activity: [
          {
            type: 'plant_identification',
            title: 'Identified plant',
            description: 'Successfully identified a plant species',
            timestamp: '2026-09-22T10:00:00Z',
            url: '/identify/0b8e',
            icon: 'leaf',
          },
          ...activity,
        ],
      })
    );
    const { container } = renderStats();

    expect(await screen.findByText('Topics')).toBeInTheDocument();
    expect(screen.queryByText('Identified plant')).not.toBeInTheDocument();
    expect(container.querySelector('a[href^="/identify"]')).toBeNull();
    expect(screen.queryByText('99')).not.toBeInTheDocument();
    expect(screen.getAllByRole('listitem')).toHaveLength(2);
  });
});
