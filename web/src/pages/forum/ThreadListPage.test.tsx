import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter, MemoryRouter } from 'react-router-dom';
import * as ReactRouter from 'react-router-dom';
import ThreadListPage from './ThreadListPage';
import { createMockCategory, createMockThread } from '../../tests/forumUtils';
import * as forumService from '../../services/forumService';

const { mockNavigate } = vi.hoisted(() => ({ mockNavigate: vi.fn() }));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useParams: vi.fn(),
    useNavigate: () => mockNavigate,
  };
});

// Mock the forumService
vi.mock('../../services/forumService');

/**
 * Helper to render ThreadListPage with Router and URL params
 */
function renderThreadListPage(initialEntries = ['/forum/plant-care']) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <ThreadListPage />
    </MemoryRouter>
  );
}

describe('ThreadListPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Mock useParams to return a hybrid id-slug; lookups use the leading id.
    vi.mocked(ReactRouter.useParams).mockReturnValue({
      categorySlug: '3-plant-care',
    });
  });

  it('shows loading spinner while fetching data', () => {
    vi.spyOn(forumService, 'fetchCategory').mockImplementation(() => new Promise(() => {}));
    vi.spyOn(forumService, 'fetchThreads').mockImplementation(() => new Promise(() => {}));

    renderThreadListPage();

    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('fetches category then threads by board slug on mount', async () => {
    const mockCategory = createMockCategory({
      slug: 'plant-care',
      name: 'Plant Care',
    });
    const mockThreads = {
      items: [createMockThread({ id: '1', title: 'Test Thread' })],
      meta: { count: 1, next: null, previous: null },
    };

    const fetchCategorySpy = vi
      .spyOn(forumService, 'fetchCategory')
      .mockResolvedValue(mockCategory);
    const fetchThreadsSpy = vi.spyOn(forumService, 'fetchThreads').mockResolvedValue(mockThreads);

    renderThreadListPage();

    await waitFor(() => {
      expect(fetchCategorySpy).toHaveBeenCalledWith(3);
      expect(fetchThreadsSpy).toHaveBeenCalledWith({
        board: 'plant-care',
        sort: '-last_activity_at',
      });
    });
  });

  it('displays category name and description', async () => {
    const mockCategory = createMockCategory({
      slug: 'plant-care',
      name: 'Plant Care Tips',
      description: 'Learn how to care for your plants',
      icon: '🌱',
    });

    vi.spyOn(forumService, 'fetchCategory').mockResolvedValue(mockCategory);
    vi.spyOn(forumService, 'fetchThreads').mockResolvedValue({
      items: [],
      meta: { count: 0 },
    });

    renderThreadListPage();

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { level: 1, name: 'Plant Care Tips' })
      ).toBeInTheDocument();
    });

    expect(screen.getByText('Learn how to care for your plants')).toBeInTheDocument();
    expect(screen.getByText('🌱')).toBeInTheDocument();
    // H9: the route sets a descriptive, category-derived document title.
    expect(document.title).toContain('Plant Care Tips');
  });

  it('renders threads when API call succeeds', async () => {
    const mockCategory = createMockCategory({ slug: 'plant-care' });
    const mockThreads = {
      items: [
        createMockThread({
          id: '1',
          title: 'How to water succulents?',
          excerpt: 'Looking for watering tips',
        }),
        createMockThread({
          id: '2',
          title: 'Best fertilizer for roses?',
          excerpt: 'Need fertilizer recommendations',
        }),
      ],
      meta: { count: 2, next: null, previous: null },
    };

    vi.spyOn(forumService, 'fetchCategory').mockResolvedValue(mockCategory);
    vi.spyOn(forumService, 'fetchThreads').mockResolvedValue(mockThreads);

    renderThreadListPage();

    await waitFor(() => {
      expect(screen.getByText('How to water succulents?')).toBeInTheDocument();
    });

    expect(screen.getByText('Best fertilizer for roses?')).toBeInTheDocument();
  });

  it('displays error message when category fetch fails', async () => {
    const errorMessage = 'Category not found';

    vi.spyOn(forumService, 'fetchCategory').mockRejectedValue(new Error(errorMessage));
    vi.spyOn(forumService, 'fetchThreads').mockRejectedValue(new Error(errorMessage));

    renderThreadListPage();

    await waitFor(() => {
      expect(screen.getByText(/Error:/i)).toBeInTheDocument();
    });

    expect(screen.getByText(errorMessage)).toBeInTheDocument();
  });

  it('shows empty state when no threads exist', async () => {
    const mockCategory = createMockCategory({ slug: 'plant-care' });

    vi.spyOn(forumService, 'fetchCategory').mockResolvedValue(mockCategory);
    vi.spyOn(forumService, 'fetchThreads').mockResolvedValue({
      items: [],
      meta: { count: 0 },
    });

    renderThreadListPage();

    await waitFor(() => {
      expect(screen.getByText('No threads found.')).toBeInTheDocument();
    });

    expect(screen.getByText(/Be the first to start a discussion!/i)).toBeInTheDocument();
  });

  it('renders breadcrumb navigation with Forums link', async () => {
    const mockCategory = createMockCategory({
      slug: 'plant-care',
      name: 'Plant Care',
    });

    vi.spyOn(forumService, 'fetchCategory').mockResolvedValue(mockCategory);
    vi.spyOn(forumService, 'fetchThreads').mockResolvedValue({
      items: [],
      meta: { count: 0 },
    });

    renderThreadListPage();

    await waitFor(() => {
      const breadcrumb = screen.getByLabelText('Breadcrumb');
      expect(breadcrumb).toBeInTheDocument();
    });

    const breadcrumb = screen.getByLabelText('Breadcrumb');
    expect(breadcrumb).toHaveTextContent('Forums');
    expect(breadcrumb).toHaveTextContent('Plant Care');
  });

  // The board search box does not filter in place — submitting redirects to the
  // dedicated /forum/search page, pre-filtered to this board. That is the honest
  // behavior (the board topics endpoint has no full-text filter); assert the redirect.
  it('search submit redirects to /forum/search pre-filtered to this board', async () => {
    const mockCategory = createMockCategory({ slug: 'plant-care' });

    vi.spyOn(forumService, 'fetchCategory').mockResolvedValue(mockCategory);
    vi.spyOn(forumService, 'fetchThreads').mockResolvedValue({
      items: [],
      meta: { count: 0 },
    });

    renderThreadListPage();

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Search this board…')).toBeInTheDocument();
    });

    await userEvent.type(screen.getByPlaceholderText('Search this board…'), 'watering');
    await userEvent.click(screen.getByText('Search'));

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/forum/search?q=watering&category=plant-care');
    });
  });

  it('re-fetches threads with the new sort when the dropdown changes', async () => {
    const mockCategory = createMockCategory({ slug: 'plant-care' });

    vi.spyOn(forumService, 'fetchCategory').mockResolvedValue(mockCategory);
    const fetchThreadsSpy = vi.spyOn(forumService, 'fetchThreads').mockResolvedValue({
      items: [],
      meta: { count: 0 },
    });

    renderThreadListPage();

    await waitFor(() => {
      expect(screen.getByDisplayValue('Recent Activity')).toBeInTheDocument();
    });

    await userEvent.selectOptions(screen.getByDisplayValue('Recent Activity'), 'Most Viewed');

    // Changing the sort provably changes the outgoing request (not just the URL).
    await waitFor(() => {
      expect(fetchThreadsSpy).toHaveBeenCalledWith({
        board: 'plant-care',
        sort: '-view_count',
      });
    });
  });

  it('shows Load More button when meta.next is present', async () => {
    const mockCategory = createMockCategory({ slug: 'plant-care' });

    vi.spyOn(forumService, 'fetchCategory').mockResolvedValue(mockCategory);
    vi.spyOn(forumService, 'fetchThreads').mockResolvedValue({
      items: Array.from({ length: 20 }, (_, i) => createMockThread({ id: `thread-${i}` })),
      meta: { count: 0, next: 'http://api/next-cursor', previous: null },
    });

    renderThreadListPage();

    await waitFor(() => {
      expect(screen.getByText('Load More')).toBeInTheDocument();
    });
  });

  it('shows an honest remaining count on Load More when the board total is known (M30)', async () => {
    const mockCategory = createMockCategory({ slug: 'plant-care', thread_count: 25 });

    vi.spyOn(forumService, 'fetchCategory').mockResolvedValue(mockCategory);
    vi.spyOn(forumService, 'fetchThreads').mockResolvedValue({
      items: Array.from({ length: 20 }, (_, i) => createMockThread({ id: `thread-${i}` })),
      meta: { count: 0, next: 'http://api/next-cursor', previous: null },
    });

    renderThreadListPage();

    // 25 total − 20 loaded = 5 remaining, not a fabricated "0 remaining".
    expect(await screen.findByText('Load More (5 remaining)')).toBeInTheDocument();
  });

  it('calls fetchThreads with cursor when Load More is clicked', async () => {
    const mockCategory = createMockCategory({ slug: 'plant-care' });
    const nextCursorUrl = 'http://api/next-cursor';

    vi.spyOn(forumService, 'fetchCategory').mockResolvedValue(mockCategory);
    const fetchThreadsSpy = vi
      .spyOn(forumService, 'fetchThreads')
      .mockResolvedValueOnce({
        items: Array.from({ length: 20 }, (_, i) => createMockThread({ id: `thread-${i}` })),
        meta: { count: 0, next: nextCursorUrl, previous: null },
      })
      .mockResolvedValueOnce({
        items: [createMockThread({ id: 'extra' })],
        meta: { count: 0, next: null, previous: null },
      });

    renderThreadListPage();

    await waitFor(() => {
      expect(screen.getByText('Load More')).toBeInTheDocument();
    });

    await userEvent.click(screen.getByText('Load More'));

    await waitFor(() => {
      expect(fetchThreadsSpy).toHaveBeenCalledWith({
        board: 'plant-care',
        cursor: nextCursorUrl,
      });
    });
  });

  it('hides Load More button when meta.next is null', async () => {
    const mockCategory = createMockCategory({ slug: 'plant-care' });

    vi.spyOn(forumService, 'fetchCategory').mockResolvedValue(mockCategory);
    vi.spyOn(forumService, 'fetchThreads').mockResolvedValue({
      items: Array.from({ length: 20 }, (_, i) => createMockThread({ id: `thread-${i}` })),
      meta: { count: 0, next: null, previous: null },
    });

    renderThreadListPage();

    await waitFor(() => {
      expect(screen.queryByText('Load More')).not.toBeInTheDocument();
    });
  });

  it('renders New Thread button with correct link', async () => {
    const mockCategory = createMockCategory({ slug: 'plant-care' });

    vi.spyOn(forumService, 'fetchCategory').mockResolvedValue(mockCategory);
    vi.spyOn(forumService, 'fetchThreads').mockResolvedValue({
      items: [],
      meta: { count: 0 },
    });

    renderThreadListPage();

    await waitFor(() => {
      const newThreadButton = screen.getByText('+ New Thread');
      expect(newThreadButton).toBeInTheDocument();
    });

    const link = screen.getByText('+ New Thread').closest('a');
    expect(link).toHaveAttribute('href', '/forum/new-thread?category=3-plant-care');
  });

  it('hides pagination when only one page exists', async () => {
    const mockCategory = createMockCategory({ slug: 'plant-care' });

    vi.spyOn(forumService, 'fetchCategory').mockResolvedValue(mockCategory);
    vi.spyOn(forumService, 'fetchThreads').mockResolvedValue({
      items: [createMockThread()],
      meta: { count: 1 },
    });

    renderThreadListPage();

    await waitFor(() => {
      expect(screen.getByText(/How to water succulents/i)).toBeInTheDocument();
    });

    expect(screen.queryByText('Previous')).not.toBeInTheDocument();
    expect(screen.queryByText('Next')).not.toBeInTheDocument();
  });

  describe('tag filter (audit M5)', () => {
    it('passes ?tag= from the URL through to the backend query', async () => {
      vi.spyOn(forumService, 'fetchCategory').mockResolvedValue(
        createMockCategory({ slug: 'plant-care', name: 'Plant Care' })
      );
      const fetchThreadsSpy = vi.spyOn(forumService, 'fetchThreads').mockResolvedValue({
        items: [createMockThread({ id: '1', title: 'Tagged Thread', tags: ['monstera'] })],
        meta: { count: 1, next: null, previous: null },
      });

      renderThreadListPage(['/forum/3-plant-care?tag=monstera']);

      await waitFor(() =>
        expect(fetchThreadsSpy).toHaveBeenCalledWith({
          board: 'plant-care',
          sort: '-last_activity_at',
          tag: 'monstera',
        })
      );
    });

    it('shows the active filter and a clear control while filtering', async () => {
      vi.spyOn(forumService, 'fetchCategory').mockResolvedValue(
        createMockCategory({ slug: 'plant-care', name: 'Plant Care' })
      );
      vi.spyOn(forumService, 'fetchThreads').mockResolvedValue({
        items: [createMockThread({ id: '1', title: 'Tagged Thread', tags: ['monstera'] })],
        meta: { count: 1, next: null, previous: null },
      });

      renderThreadListPage(['/forum/3-plant-care?tag=monstera']);

      await waitFor(() => expect(screen.getByText(/filtered by tag/i)).toBeInTheDocument());
      expect(screen.getByRole('button', { name: /clear filter/i })).toBeInTheDocument();
    });

    it('re-queries with the tag when a tag chip is clicked', async () => {
      vi.spyOn(forumService, 'fetchCategory').mockResolvedValue(
        createMockCategory({ slug: 'plant-care', name: 'Plant Care' })
      );
      const fetchThreadsSpy = vi.spyOn(forumService, 'fetchThreads').mockResolvedValue({
        items: [createMockThread({ id: '1', title: 'Tagged Thread', tags: ['monstera'] })],
        meta: { count: 1, next: null, previous: null },
      });

      renderThreadListPage(['/forum/3-plant-care']);

      await waitFor(() => expect(screen.getByText('Tagged Thread')).toBeInTheDocument());
      await userEvent.click(screen.getByRole('button', { name: '#monstera' }));

      await waitFor(() =>
        expect(fetchThreadsSpy).toHaveBeenLastCalledWith(
          expect.objectContaining({ tag: 'monstera' })
        )
      );
    });

    it('explains an empty result as a filter miss, not an empty board', async () => {
      vi.spyOn(forumService, 'fetchCategory').mockResolvedValue(
        createMockCategory({ slug: 'plant-care', name: 'Plant Care' })
      );
      vi.spyOn(forumService, 'fetchThreads').mockResolvedValue({
        items: [],
        meta: { count: 0, next: null, previous: null },
      });

      renderThreadListPage(['/forum/3-plant-care?tag=nope']);

      await waitFor(() => expect(screen.getByText(/no threads tagged #nope/i)).toBeInTheDocument());
      expect(screen.queryByText(/be the first to start a discussion/i)).not.toBeInTheDocument();
    });
  });

  it('drops the stale Load More while a tag reload is in flight (review repair)', async () => {
    // The old cursor addresses the PREVIOUS result set. Left visible, a click
    // during the reload would append wrong-filter rows and then overwrite the
    // new cursor with a stale one — and the loadGen guard cannot catch it,
    // because handleLoadMore reads loadGenRef at CLICK time, by which point the
    // reload has already bumped it to the same value.
    vi.spyOn(forumService, 'fetchCategory').mockResolvedValue(
      createMockCategory({ slug: 'plant-care', name: 'Plant Care' })
    );
    vi.spyOn(forumService, 'fetchThreads')
      .mockResolvedValueOnce({
        items: [createMockThread({ id: '1', title: 'Tagged Thread', tags: ['monstera'] })],
        meta: { count: 50, next: 'https://api.test/cursor=stale', previous: null },
      })
      // The tag-filtered reload never settles, so we observe the in-flight state.
      .mockImplementationOnce(() => new Promise(() => {}));

    renderThreadListPage(['/forum/3-plant-care']);

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /load more/i })).toBeInTheDocument()
    );

    await userEvent.click(screen.getByRole('button', { name: '#monstera' }));

    await waitFor(() =>
      expect(screen.queryByRole('button', { name: /load more/i })).not.toBeInTheDocument()
    );
  });

  it('drops the remaining-count from Load More while a tag filter is active', async () => {
    // category.thread_count is the board's UNFILTERED total, so subtracting the
    // filtered page length invents a number ("380 remaining" for a 25-result
    // filter) — the exact dishonest-count class audit M30 removed.
    vi.spyOn(forumService, 'fetchCategory').mockResolvedValue(
      createMockCategory({ slug: 'plant-care', name: 'Plant Care', thread_count: 400 })
    );
    vi.spyOn(forumService, 'fetchThreads').mockResolvedValue({
      items: [createMockThread({ id: '1', title: 'Tagged Thread', tags: ['monstera'] })],
      meta: { count: 25, next: 'https://api.test/cursor=next', previous: null },
    });

    renderThreadListPage(['/forum/3-plant-care?tag=monstera']);

    const button = await screen.findByRole('button', { name: /load more/i });
    expect(button).toHaveTextContent('Load More');
    expect(button).not.toHaveTextContent('remaining');
  });

  it('still shows the honest remaining-count when no tag filter is active', async () => {
    vi.spyOn(forumService, 'fetchCategory').mockResolvedValue(
      createMockCategory({ slug: 'plant-care', name: 'Plant Care', thread_count: 400 })
    );
    vi.spyOn(forumService, 'fetchThreads').mockResolvedValue({
      items: [createMockThread({ id: '1', title: 'A Thread' })],
      meta: { count: 400, next: 'https://api.test/cursor=next', previous: null },
    });

    renderThreadListPage(['/forum/3-plant-care']);

    const button = await screen.findByRole('button', { name: /load more/i });
    expect(button).toHaveTextContent('399 remaining');
  });
});
