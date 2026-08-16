import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import ActiveNowModule from './ActiveNowModule';
import type { RecentTopic } from '../../../types/forum';

const mockFetchRecentTopics = vi.fn();
vi.mock('../../../services/forumService', () => ({
  fetchRecentTopics: (...args: unknown[]) => mockFetchRecentTopics(...args),
}));

function topic(overrides: Partial<RecentTopic> = {}): RecentTopic {
  return {
    id: 1,
    slug: 'monstera-yellow-leaves',
    title: 'Monstera leaves turning yellow',
    board: { id: 2, name: 'Care Problems', slug: 'care-problems' },
    reply_count: 3,
    last_post_at: '2026-08-01T00:00:00Z',
    is_pinned: false,
    thumbnail_url: null,
    ...overrides,
  };
}

function renderModule(props: { topics?: RecentTopic[] } = {}) {
  return render(
    <MemoryRouter>
      <ActiveNowModule {...props} />
    </MemoryRouter>
  );
}

describe('ActiveNowModule', () => {
  // Block body — see CommunityExpertsModule.test.tsx / FromTheBlogModule.test.tsx
  // for why (Vitest 4 mockReset:true teardown-vs-implicit-return interaction).
  beforeEach(() => {
    mockFetchRecentTopics.mockReset();
  });

  describe('self-fetching (no topics prop)', () => {
    it('fetches its own capped page and renders the results', async () => {
      mockFetchRecentTopics.mockResolvedValue([topic()]);
      renderModule();

      const link = await screen.findByRole('link', { name: /monstera leaves turning yellow/i });
      expect(link).toHaveAttribute('href', '/forum/2-care-problems/1-monstera-yellow-leaves');
      expect(mockFetchRecentTopics).toHaveBeenCalledWith(3);
      expect(screen.getByText('Active now')).toBeInTheDocument();
    });

    it('renders nothing when the fetch resolves empty', async () => {
      mockFetchRecentTopics.mockResolvedValue([]);
      const { container } = renderModule();

      await waitFor(() => expect(mockFetchRecentTopics).toHaveBeenCalled());
      expect(container).toBeEmptyDOMElement();
    });

    it('renders nothing on fetch error', async () => {
      mockFetchRecentTopics.mockRejectedValue(new Error('nope'));
      const { container } = renderModule();

      await waitFor(() => expect(mockFetchRecentTopics).toHaveBeenCalled());
      expect(container).toBeEmptyDOMElement();
    });

    it('caps at 3 rows even if the backend somehow returns more', async () => {
      mockFetchRecentTopics.mockResolvedValue([
        topic({ id: 1, slug: 't1', title: 'Topic one' }),
        topic({ id: 2, slug: 't2', title: 'Topic two' }),
        topic({ id: 3, slug: 't3', title: 'Topic three' }),
        topic({ id: 4, slug: 't4', title: 'Topic four' }),
        topic({ id: 5, slug: 't5', title: 'Topic five' }),
      ]);
      renderModule();

      await screen.findByText('Topic one');
      expect(screen.getAllByRole('listitem')).toHaveLength(3);
      expect(screen.queryByText('Topic four')).not.toBeInTheDocument();
      expect(screen.queryByText('Topic five')).not.toBeInTheDocument();
    });
  });

  describe('with a topics prop (page-provided rows)', () => {
    it('renders the provided rows without calling fetchRecentTopics', async () => {
      renderModule({ topics: [topic()] });

      await screen.findByText('Monstera leaves turning yellow');
      expect(mockFetchRecentTopics).not.toHaveBeenCalled();
    });

    // Controller Ruling 3: ActiveNowModule renders AT MOST 3 rows regardless
    // of source. CategoryListPage passes its 5-row bloom-watch-hero fetch
    // straight through — the module, not the page, is responsible for the cap.
    it('slices to at most 3 rows when the page passes 5', async () => {
      const topics = [
        topic({ id: 1, slug: 't1', title: 'Topic one' }),
        topic({ id: 2, slug: 't2', title: 'Topic two' }),
        topic({ id: 3, slug: 't3', title: 'Topic three' }),
        topic({ id: 4, slug: 't4', title: 'Topic four' }),
        topic({ id: 5, slug: 't5', title: 'Topic five' }),
      ];
      renderModule({ topics });

      await screen.findByText('Topic one');
      expect(screen.getAllByRole('listitem')).toHaveLength(3);
      expect(screen.getByText('Topic two')).toBeInTheDocument();
      expect(screen.getByText('Topic three')).toBeInTheDocument();
      expect(screen.queryByText('Topic four')).not.toBeInTheDocument();
      expect(screen.queryByText('Topic five')).not.toBeInTheDocument();
      expect(mockFetchRecentTopics).not.toHaveBeenCalled();
    });

    it('renders nothing when the provided topics array is empty', () => {
      const { container } = renderModule({ topics: [] });

      expect(container).toBeEmptyDOMElement();
      expect(mockFetchRecentTopics).not.toHaveBeenCalled();
    });
  });

  it('renders a thumbnail image when the topic has one', async () => {
    renderModule({ topics: [topic({ thumbnail_url: 'https://example.com/thumb.jpg' })] });

    await screen.findByText('Monstera leaves turning yellow');
    const row = screen.getByRole('listitem');
    expect(row.querySelector('img')).toHaveAttribute('src', 'https://example.com/thumb.jpg');
  });

  it('renders the board icon tile (no thumbnail image) when thumbnail_url is null', async () => {
    renderModule({ topics: [topic({ thumbnail_url: null })] });

    await screen.findByText('Monstera leaves turning yellow');
    const row = screen.getByRole('listitem');
    expect(row.querySelector('img')).not.toBeInTheDocument();
    expect(row.querySelector('svg')).toBeInTheDocument();
  });

  it('pluralizes the reply count', async () => {
    renderModule({
      topics: [
        topic({ id: 1, slug: 'one-reply', title: 'One reply topic', reply_count: 1 }),
        topic({ id: 2, slug: 'two-replies', title: 'Two replies topic', reply_count: 2 }),
      ],
    });

    await screen.findByText('One reply topic');
    const rows = screen.getAllByRole('listitem');
    expect(rows[0]).toHaveTextContent('1 reply');
    expect(rows[0]).not.toHaveTextContent('replies');
    expect(rows[1]).toHaveTextContent('2 replies');
  });

  it('renders a relative timestamp when last_post_at is present', async () => {
    renderModule({ topics: [topic({ last_post_at: '2026-08-01T00:00:00Z' })] });

    await screen.findByText('Monstera leaves turning yellow');
    const row = screen.getByRole('listitem');
    expect(row.querySelector('time')).toBeInTheDocument();
  });

  it('omits the timestamp when last_post_at is null', async () => {
    renderModule({ topics: [topic({ last_post_at: null, reply_count: 4 })] });

    await screen.findByText('Monstera leaves turning yellow');
    const row = screen.getByRole('listitem');
    expect(row.querySelector('time')).not.toBeInTheDocument();
    expect(row).toHaveTextContent('4 replies');
  });
});
