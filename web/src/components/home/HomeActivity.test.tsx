import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import HomeActivity from './HomeActivity';
import * as forumService from '../../services/forumService';
import { logger } from '../../utils/logger';
import type { ForumMyStats, RecentTopic } from '../../types/forum';

vi.mock('../../services/forumService');

vi.mock('../../utils/logger', () => ({
  logger: { error: vi.fn(), warn: vi.fn(), info: vi.fn(), debug: vi.fn() },
}));

function makeMyStats(overrides: Partial<ForumMyStats> = {}): ForumMyStats {
  return {
    posts: 12,
    solutions_accepted: 3,
    identifications_shared: 7,
    streak_days: 4,
    badge_name: 'Botanist',
    badge_progress: 7,
    badge_target: 20,
    badges: [],
    ...overrides,
  };
}

function makeTopic(overrides: Partial<RecentTopic> = {}): RecentTopic {
  return {
    id: 42,
    slug: 'monstera-leaf-curl',
    title: 'Monstera leaf curl',
    board: { id: 7, name: 'Care & problems', slug: 'care-problems' },
    reply_count: 3,
    last_post_at: '2026-09-01T10:00:00Z',
    is_pinned: false,
    thumbnail_url: null,
    ...overrides,
  };
}

const renderActivity = () =>
  render(
    <BrowserRouter>
      <HomeActivity />
    </BrowserRouter>
  );

describe('HomeActivity', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Both mocks are set fresh per test: vitest.config.ts's global
    // `mockReset: true` wipes any factory-chained value before every test.
    vi.mocked(forumService.fetchMyStats).mockResolvedValue(makeMyStats());
    vi.mocked(forumService.fetchRecentTopics).mockResolvedValue([makeTopic()]);
  });

  it('renders both sections from the two existing endpoints', async () => {
    renderActivity();

    expect(await screen.findByRole('heading', { name: 'Your season' })).toBeInTheDocument();
    expect(await screen.findByRole('heading', { name: 'Active now' })).toBeInTheDocument();
    expect(screen.getByText('Identifications')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /monstera leaf curl/i })).toBeInTheDocument();
  });

  it('links each row to the topic and the section to the forum', async () => {
    renderActivity();

    const row = await screen.findByRole('link', { name: /monstera leaf curl/i });
    // Same /forum/{boardId}-{boardSlug}/{topicId}-{topicSlug} shape the rail uses.
    expect(row).toHaveAttribute('href', '/forum/7-care-problems/42-monstera-leaf-curl');
    expect(screen.getByRole('link', { name: /all discussions/i })).toHaveAttribute(
      'href',
      '/forum'
    );
  });

  it('renders the singular reply label and the board name on a row', async () => {
    vi.mocked(forumService.fetchRecentTopics).mockResolvedValue([makeTopic({ reply_count: 1 })]);
    renderActivity();

    expect(await screen.findByText(/Care & problems · 1 reply/)).toBeInTheDocument();
  });

  it('caps the list at five rows even when the API returns more', async () => {
    vi.mocked(forumService.fetchRecentTopics).mockResolvedValue(
      Array.from({ length: 9 }, (_, i) =>
        makeTopic({ id: i + 1, slug: `topic-${i + 1}`, title: `Topic ${i + 1}` })
      )
    );
    renderActivity();

    await screen.findByRole('heading', { name: 'Active now' });
    expect(screen.getAllByRole('listitem')).toHaveLength(5);
  });

  it('requests only five rows', async () => {
    renderActivity();

    await waitFor(() => expect(forumService.fetchRecentTopics).toHaveBeenCalledWith(5));
  });

  it('hides the stats half — but keeps Active now — when me/stats fails', async () => {
    vi.mocked(forumService.fetchMyStats).mockRejectedValue(new Error('boom'));
    renderActivity();

    expect(await screen.findByRole('heading', { name: 'Active now' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Your season' })).not.toBeInTheDocument();
    expect(logger.error).toHaveBeenCalledWith(
      'Error loading home stats',
      expect.objectContaining({ component: 'HomeActivity' })
    );
  });

  it('hides the Active now half — but keeps the stats — when topics/recent fails', async () => {
    vi.mocked(forumService.fetchRecentTopics).mockRejectedValue(new Error('boom'));
    renderActivity();

    expect(await screen.findByRole('heading', { name: 'Your season' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Active now' })).not.toBeInTheDocument();
    expect(logger.error).toHaveBeenCalledWith(
      'Error loading home recent topics',
      expect.objectContaining({ component: 'HomeActivity' })
    );
  });

  it('renders nothing at all when both fetches fail', async () => {
    vi.mocked(forumService.fetchMyStats).mockRejectedValue(new Error('boom'));
    vi.mocked(forumService.fetchRecentTopics).mockRejectedValue(new Error('boom'));
    const { container } = renderActivity();

    await waitFor(() => expect(logger.error).toHaveBeenCalledTimes(2));
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing while both fetches are still in flight', () => {
    vi.mocked(forumService.fetchMyStats).mockImplementation(() => new Promise(() => {}));
    vi.mocked(forumService.fetchRecentTopics).mockImplementation(() => new Promise(() => {}));
    const { container } = renderActivity();

    // No spinner, no empty shell — Home must not show loading chrome for a
    // section that is a nice-to-have on top of the marketing page.
    expect(container).toBeEmptyDOMElement();
  });

  it('renders the thumbnail instead of the board tile when the topic has one', async () => {
    vi.mocked(forumService.fetchRecentTopics).mockResolvedValue([
      makeTopic({ thumbnail_url: 'https://cdn.example.com/leaf.jpg' }),
    ]);
    const { container } = renderActivity();

    await screen.findByRole('heading', { name: 'Active now' });
    const img = container.querySelector('img');
    expect(img).toHaveAttribute('src', 'https://cdn.example.com/leaf.jpg');
    // Decorative: the row's accessible name comes from the title text.
    expect(img).toHaveAttribute('alt', '');
  });

  it('omits the timestamp when last_post_at is null', async () => {
    vi.mocked(forumService.fetchRecentTopics).mockResolvedValue([
      makeTopic({ last_post_at: null }),
    ]);
    const { container } = renderActivity();

    await screen.findByRole('heading', { name: 'Active now' });
    expect(container.querySelector('time')).toBeNull();
  });
});
