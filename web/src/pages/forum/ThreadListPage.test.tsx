import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter, MemoryRouter } from 'react-router-dom';
import * as ReactRouter from 'react-router-dom';
import ThreadListPage from './ThreadListPage';
import { createMockCategory, createMockForum, createMockThread } from '../../tests/forumUtils';
import * as forumService from '../../services/forumService';
import * as blogService from '../../services/blogService';
import { AuthContext, type AuthContextValue } from '../../contexts/AuthContext';
import type { Forum } from '@/types';

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

// Defensive mock for FromTheBlogModule's rail fetch. RailSlot portals into
// `#app-rail`, which doesn't exist in jsdom for this suite — so the module
// never actually mounts and this fetch is never called — but the mock guards
// against a real network call if that changes.
vi.mock('../../services/blogService');

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
    // Set fresh each test (not chained at module scope): vitest.config.ts's
    // global `mockReset: true` wipes any factory-chained mock value before
    // every test.
    vi.mocked(blogService.fetchPopularPosts).mockResolvedValue([]);
  });

  it('shows loading spinner while fetching data', () => {
    vi.spyOn(forumService, 'fetchForum').mockImplementation(() => new Promise(() => {}));
    vi.spyOn(forumService, 'fetchThreads').mockImplementation(() => new Promise(() => {}));

    renderThreadListPage();

    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('fetches category then threads by board slug on mount', async () => {
    const mockCategory = createMockForum({
      slug: 'plant-care',
      name: 'Plant Care',
    });
    const mockThreads = {
      items: [createMockThread({ id: '1', title: 'Test Thread' })],
      meta: { count: 1, next: null, previous: null },
    };

    const fetchCategorySpy = vi.spyOn(forumService, 'fetchForum').mockResolvedValue(mockCategory);
    const fetchThreadsSpy = vi.spyOn(forumService, 'fetchThreads').mockResolvedValue(mockThreads);

    renderThreadListPage();

    await waitFor(() => {
      expect(fetchCategorySpy).toHaveBeenCalledWith(3);
      // No ?order= sends no sort: the backend applies the forum's own
      // default sort (todo 669).
      expect(fetchThreadsSpy).toHaveBeenCalledWith({
        board: 'plant-care',
        sort: undefined,
      });
    });
  });

  it('displays category name and description', async () => {
    const mockCategory = createMockForum({
      slug: 'plant-care',
      name: 'Plant Care Tips',
      description: 'Learn how to care for your plants',
      icon: '🌱',
    });

    vi.spyOn(forumService, 'fetchForum').mockResolvedValue(mockCategory);
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

  it("drops board A's header while board B loads instead of showing it over B's skeleton", async () => {
    const boardA = createMockForum({ id: 'cat-3', slug: 'plant-care', name: 'Plant Care' });
    const boardB = createMockForum({ id: 'cat-4', slug: 'pests', name: 'Pests' });
    let resolveB: (value: ReturnType<typeof createMockForum>) => void = () => {};
    vi.spyOn(forumService, 'fetchForum').mockImplementation((id) =>
      id === 3
        ? Promise.resolve(boardA)
        : new Promise((resolve) => {
            resolveB = resolve;
          })
    );
    vi.spyOn(forumService, 'fetchThreads').mockResolvedValue({ items: [], meta: { count: 0 } });

    const { rerender } = renderThreadListPage();
    await screen.findByRole('heading', { level: 1, name: 'Plant Care' });

    // Navigate A → B: useParams is mocked, so swap its value and re-render.
    vi.mocked(ReactRouter.useParams).mockReturnValue({ categorySlug: '4-pests' });
    rerender(
      <MemoryRouter initialEntries={['/forum/4-pests']}>
        <ThreadListPage />
      </MemoryRouter>
    );

    // While B is in flight: no trace of A, and the (header) skeleton is up.
    await waitFor(() => {
      expect(screen.queryByRole('heading', { level: 1, name: 'Plant Care' })).toBeNull();
    });
    expect(screen.queryByText('Plant Care')).toBeNull();
    expect(screen.getByRole('status')).toBeInTheDocument();

    resolveB(boardB);
    await screen.findByRole('heading', { level: 1, name: 'Pests' });
  });

  it('restores the cached board header when navigating back before the new board resolves', async () => {
    const boardA = createMockForum({ id: 'cat-3', slug: 'plant-care', name: 'Plant Care' });
    const fetchCategorySpy = vi
      .spyOn(forumService, 'fetchForum')
      .mockImplementation((id) => (id === 3 ? Promise.resolve(boardA) : new Promise(() => {})));
    vi.spyOn(forumService, 'fetchThreads').mockResolvedValue({ items: [], meta: { count: 0 } });

    const { rerender } = renderThreadListPage();
    await screen.findByRole('heading', { level: 1, name: 'Plant Care' });

    vi.mocked(ReactRouter.useParams).mockReturnValue({ categorySlug: '4-pests' });
    rerender(
      <MemoryRouter initialEntries={['/forum/4-pests']}>
        <ThreadListPage />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.queryByRole('heading', { level: 1, name: 'Plant Care' })).toBeNull();
    });

    // Back to A while B is still pending: A is served from the cache, and the
    // header must come back with it (review round 1: the cache-hit path used
    // to skip setCategory, leaving an empty h1).
    vi.mocked(ReactRouter.useParams).mockReturnValue({ categorySlug: '3-plant-care' });
    rerender(
      <MemoryRouter initialEntries={['/forum/3-plant-care']}>
        <ThreadListPage />
      </MemoryRouter>
    );
    await screen.findByRole('heading', { level: 1, name: 'Plant Care' });
    await waitFor(() => expect(screen.queryByRole('status')).toBeNull());
    // A came from the cache: one fetch per board, never a re-fetch of A.
    expect(fetchCategorySpy).toHaveBeenCalledTimes(2);
  });

  it('shows the error state, not an empty board, when the category loads but the threads fetch fails', async () => {
    vi.spyOn(forumService, 'fetchForum').mockResolvedValue(
      createMockForum({ slug: 'plant-care', name: 'Plant Care' })
    );
    vi.spyOn(forumService, 'fetchThreads').mockRejectedValue(new Error('Server error'));

    renderThreadListPage();

    await screen.findByRole('heading', { level: 1, name: 'Plant Care' });
    expect(await screen.findByText(/Server error/)).toBeInTheDocument();
    expect(screen.queryByText('No threads found.')).toBeNull();
    // The board chrome and the error coexist — not a full-page error state.
    expect(screen.getByRole('heading', { level: 1, name: 'Plant Care' })).toBeInTheDocument();
  });

  it('renders threads when API call succeeds', async () => {
    const mockCategory = createMockForum({ slug: 'plant-care' });
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

    vi.spyOn(forumService, 'fetchForum').mockResolvedValue(mockCategory);
    vi.spyOn(forumService, 'fetchThreads').mockResolvedValue(mockThreads);

    renderThreadListPage();

    await waitFor(() => {
      expect(screen.getByText('How to water succulents?')).toBeInTheDocument();
    });

    expect(screen.getByText('Best fertilizer for roses?')).toBeInTheDocument();
  });

  it('displays error message when category fetch fails', async () => {
    const errorMessage = 'Category not found';

    vi.spyOn(forumService, 'fetchForum').mockRejectedValue(new Error(errorMessage));
    vi.spyOn(forumService, 'fetchThreads').mockRejectedValue(new Error(errorMessage));

    renderThreadListPage();

    await waitFor(() => {
      expect(screen.getByText(/Error:/i)).toBeInTheDocument();
    });

    expect(screen.getByText(errorMessage)).toBeInTheDocument();
  });

  it('shows empty state when no threads exist', async () => {
    const mockCategory = createMockForum({ slug: 'plant-care' });

    vi.spyOn(forumService, 'fetchForum').mockResolvedValue(mockCategory);
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

  it('renders breadcrumb navigation with Forum link', async () => {
    const mockCategory = createMockForum({
      slug: 'plant-care',
      name: 'Plant Care',
    });

    vi.spyOn(forumService, 'fetchForum').mockResolvedValue(mockCategory);
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
    expect(breadcrumb).toHaveTextContent('Forum');
    expect(breadcrumb).toHaveTextContent('Plant Care');
  });

  // The board search box does not filter in place — submitting redirects to the
  // dedicated /forum/search page, pre-filtered to this board. That is the honest
  // behavior (the board topics endpoint has no full-text filter); assert the redirect.
  it('search submit redirects to /forum/search pre-filtered to this board', async () => {
    const mockCategory = createMockForum({ slug: 'plant-care' });

    vi.spyOn(forumService, 'fetchForum').mockResolvedValue(mockCategory);
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

  it('re-fetches threads with the new sort when a sort chip is clicked', async () => {
    const mockCategory = createMockForum({ slug: 'plant-care' });

    vi.spyOn(forumService, 'fetchForum').mockResolvedValue(mockCategory);
    const fetchThreadsSpy = vi.spyOn(forumService, 'fetchThreads').mockResolvedValue({
      items: [],
      meta: { count: 0 },
    });

    renderThreadListPage();

    // Default sort ("Active" = -last_activity_at) is reflected as the pressed chip.
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Active' })).toHaveAttribute(
        'aria-pressed',
        'true'
      );
    });

    await userEvent.click(screen.getByRole('button', { name: 'Most viewed' }));

    // Changing the sort provably changes the outgoing request (not just the URL).
    await waitFor(() => {
      expect(fetchThreadsSpy).toHaveBeenCalledWith({
        board: 'plant-care',
        sort: '-view_count',
      });
    });

    expect(screen.getByRole('button', { name: 'Most viewed' })).toHaveAttribute(
      'aria-pressed',
      'true'
    );
    expect(screen.getByRole('button', { name: 'Active' })).toHaveAttribute('aria-pressed', 'false');
  });

  it('shows Load More button when meta.next is present', async () => {
    const mockCategory = createMockForum({ slug: 'plant-care' });

    vi.spyOn(forumService, 'fetchForum').mockResolvedValue(mockCategory);
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
    const mockCategory = createMockForum({ slug: 'plant-care', thread_count: 25 });

    vi.spyOn(forumService, 'fetchForum').mockResolvedValue(mockCategory);
    vi.spyOn(forumService, 'fetchThreads').mockResolvedValue({
      items: Array.from({ length: 20 }, (_, i) => createMockThread({ id: `thread-${i}` })),
      meta: { count: 0, next: 'http://api/next-cursor', previous: null },
    });

    renderThreadListPage();

    // 25 total − 20 loaded = 5 remaining, not a fabricated "0 remaining".
    expect(await screen.findByText('Load More (5 remaining)')).toBeInTheDocument();
  });

  it('calls fetchThreads with cursor when Load More is clicked', async () => {
    const mockCategory = createMockForum({ slug: 'plant-care' });
    const nextCursorUrl = 'http://api/next-cursor';

    vi.spyOn(forumService, 'fetchForum').mockResolvedValue(mockCategory);
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
    const mockCategory = createMockForum({ slug: 'plant-care' });

    vi.spyOn(forumService, 'fetchForum').mockResolvedValue(mockCategory);
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
    const mockCategory = createMockForum({ slug: 'plant-care' });

    vi.spyOn(forumService, 'fetchForum').mockResolvedValue(mockCategory);
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
    const mockCategory = createMockForum({ slug: 'plant-care' });

    vi.spyOn(forumService, 'fetchForum').mockResolvedValue(mockCategory);
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
      vi.spyOn(forumService, 'fetchForum').mockResolvedValue(
        createMockForum({ slug: 'plant-care', name: 'Plant Care' })
      );
      const fetchThreadsSpy = vi.spyOn(forumService, 'fetchThreads').mockResolvedValue({
        items: [createMockThread({ id: '1', title: 'Tagged Thread', tags: ['monstera'] })],
        meta: { count: 1, next: null, previous: null },
      });

      renderThreadListPage(['/forum/3-plant-care?tag=monstera']);

      await waitFor(() =>
        expect(fetchThreadsSpy).toHaveBeenCalledWith({
          board: 'plant-care',
          sort: undefined,
          tag: 'monstera',
        })
      );
    });

    it('shows the active filter and a clear control while filtering', async () => {
      vi.spyOn(forumService, 'fetchForum').mockResolvedValue(
        createMockForum({ slug: 'plant-care', name: 'Plant Care' })
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
      vi.spyOn(forumService, 'fetchForum').mockResolvedValue(
        createMockForum({ slug: 'plant-care', name: 'Plant Care' })
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
      vi.spyOn(forumService, 'fetchForum').mockResolvedValue(
        createMockForum({ slug: 'plant-care', name: 'Plant Care' })
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
    vi.spyOn(forumService, 'fetchForum').mockResolvedValue(
      createMockForum({ slug: 'plant-care', name: 'Plant Care' })
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
    vi.spyOn(forumService, 'fetchForum').mockResolvedValue(
      createMockForum({ slug: 'plant-care', name: 'Plant Care', thread_count: 400 })
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
    vi.spyOn(forumService, 'fetchForum').mockResolvedValue(
      createMockForum({ slug: 'plant-care', name: 'Plant Care', thread_count: 400 })
    );
    vi.spyOn(forumService, 'fetchThreads').mockResolvedValue({
      items: [createMockThread({ id: '1', title: 'A Thread' })],
      meta: { count: 400, next: 'https://api.test/cursor=next', previous: null },
    });

    renderThreadListPage(['/forum/3-plant-care']);

    const button = await screen.findByRole('button', { name: /load more/i });
    expect(button).toHaveTextContent('399 remaining');
  });

  it('shows the Category › Forum breadcrumb once the category resolves (todo 665)', async () => {
    const forum = createMockForum({ id: '3', slug: 'plant-care', name: 'Plant Care' });
    vi.spyOn(forumService, 'fetchForum').mockResolvedValue(forum);
    vi.spyOn(forumService, 'fetchThreads').mockResolvedValue({ items: [], meta: { count: 0 } });
    vi.mocked(forumService.fetchForumCategory).mockResolvedValue(
      createMockCategory({ id: '1', name: 'Indoor plants', forums: [forum] })
    );

    renderThreadListPage();

    const crumbs = await screen.findByRole('navigation', { name: 'Breadcrumb' });
    await waitFor(() =>
      expect(crumbs.textContent?.replace(/\s+/g, '')).toBe('Forum/Indoorplants/PlantCare')
    );
    expect(forumService.fetchForumCategory).toHaveBeenCalledWith('3');
  });

  it('keeps the two-level breadcrumb when the category cannot be told', async () => {
    const forum = createMockForum({ id: '3', slug: 'plant-care', name: 'Plant Care' });
    vi.spyOn(forumService, 'fetchForum').mockResolvedValue(forum);
    vi.spyOn(forumService, 'fetchThreads').mockResolvedValue({ items: [], meta: { count: 0 } });
    vi.mocked(forumService.fetchForumCategory).mockResolvedValue(null);

    renderThreadListPage();

    const crumbs = await screen.findByRole('navigation', { name: 'Breadcrumb' });
    await waitFor(() => expect(forumService.fetchForumCategory).toHaveBeenCalledWith('3'));
    expect(crumbs.textContent?.replace(/\s+/g, '')).toBe('Forum/PlantCare');
  });
  describe('Mark forum read (todo 671)', () => {
    const forum = createMockForum({ id: '3', slug: 'plant-care', name: 'Plant Care' });

    it('marks the forum read and clears the unread threads', async () => {
      vi.spyOn(forumService, 'fetchForum').mockResolvedValue(forum);
      vi.spyOn(forumService, 'fetchThreads').mockResolvedValue({
        items: [createMockThread({ id: '1', title: 'Unread one', is_unread: true })],
        meta: { count: 1, next: null, previous: null },
      });
      vi.mocked(forumService.markForumRead).mockResolvedValue(undefined);

      renderThreadListPage();
      await userEvent.click(await screen.findByRole('button', { name: 'Mark forum read' }));

      expect(forumService.markForumRead).toHaveBeenCalledWith('plant-care');
      await waitFor(() =>
        expect(screen.queryByRole('button', { name: 'Mark forum read' })).not.toBeInTheDocument()
      );
      expect(screen.queryByText('New')).not.toBeInTheDocument();
    });

    it('is not offered when nothing is unread (and never to a guest)', async () => {
      vi.spyOn(forumService, 'fetchForum').mockResolvedValue(forum);
      vi.spyOn(forumService, 'fetchThreads').mockResolvedValue({
        items: [createMockThread({ id: '1', title: 'Read one', is_unread: false })],
        meta: { count: 1, next: null, previous: null },
      });

      renderThreadListPage();
      await screen.findByText('Read one');

      expect(screen.queryByRole('button', { name: 'Mark forum read' })).not.toBeInTheDocument();
    });
  });

  describe('a locked password forum (todo 680)', () => {
    it('shows the unlock form and never fetches its threads', async () => {
      vi.mocked(forumService.fetchForum).mockResolvedValue(
        createMockForum({ slug: 'club', name: 'Club', is_locked: true })
      );

      renderThreadListPage();

      expect(await screen.findByText('This forum needs a password.')).toBeInTheDocument();
      expect(screen.getByRole('heading', { level: 1, name: 'Club' })).toBeInTheDocument();
      expect(forumService.fetchThreads).not.toHaveBeenCalled();
    });

    it('re-reads the forum and lists its threads once unlocked', async () => {
      vi.mocked(forumService.fetchForum)
        .mockResolvedValueOnce(createMockForum({ slug: 'club', name: 'Club', is_locked: true }))
        .mockResolvedValue(createMockForum({ slug: 'club', name: 'Club', is_locked: false }));
      vi.mocked(forumService.unlockForum).mockResolvedValue(undefined);
      vi.mocked(forumService.fetchThreads).mockResolvedValue({
        items: [createMockThread({ id: '1', title: 'Club meeting' })],
        meta: { count: 1, next: null, previous: null },
      });

      renderThreadListPage();
      await userEvent.type(await screen.findByLabelText('Password'), 'secret');
      await userEvent.click(screen.getByRole('button', { name: 'Unlock' }));

      expect(await screen.findByText('Club meeting')).toBeInTheDocument();
      expect(forumService.unlockForum).toHaveBeenCalledWith('club', 'secret');
      expect(forumService.fetchForum).toHaveBeenCalledTimes(2);
      expect(forumService.fetchThreads).toHaveBeenCalledWith(
        expect.objectContaining({ board: 'club' })
      );
    });
  });

  describe('forum display settings, theme, capabilities and watch level (todos 669, 672, 677, 681)', () => {
    const forum = createMockForum({ id: '3', slug: 'plant-care', name: 'Plant Care', icon: '' });

    function withRow(row: Partial<Forum>) {
      vi.spyOn(forumService, 'fetchForum').mockResolvedValue(forum);
      vi.spyOn(forumService, 'fetchThreads').mockResolvedValue({ items: [], meta: { count: 0 } });
      vi.mocked(forumService.fetchForumCategory).mockResolvedValue(
        createMockCategory({ id: '1', name: 'Indoor', forums: [{ ...forum, ...row }] })
      );
    }

    function renderSignedIn() {
      return render(
        <AuthContext value={{ isAuthenticated: true } as AuthContextValue}>
          <MemoryRouter initialEntries={['/forum/3-plant-care']}>
            <ThreadListPage />
          </MemoryRouter>
        </AuthContext>
      );
    }

    const allowed = { can_post: true, can_reply: true, can_poll: true, can_attach: true };

    it('renders the rules panel with its link', async () => {
      withRow({
        rules: 'Be kind.\nNo spam.',
        rules_url: 'https://example.com/rules',
        capabilities: allowed,
      });
      renderThreadListPage(['/forum/3-plant-care']);

      const panel = await screen.findByRole('region', { name: 'Forum rules' });
      expect(panel).toHaveTextContent('Be kind.');
      expect(panel).toHaveTextContent('No spam.');
      expect(screen.getByRole('link', { name: 'Read the full rules' })).toHaveAttribute(
        'href',
        'https://example.com/rules'
      );
    });

    it('shows no rules panel when the forum has none', async () => {
      withRow({ rules: '', rules_url: '', capabilities: allowed });
      renderThreadListPage(['/forum/3-plant-care']);
      await screen.findByRole('link', { name: '+ New Thread' });
      expect(screen.queryByRole('region', { name: 'Forum rules' })).not.toBeInTheDocument();
    });

    it('shows a closed forum as closed and offers no composer', async () => {
      withRow({
        is_closed: true,
        capabilities: { can_post: false, can_reply: false, can_poll: false, can_attach: false },
      });
      renderSignedIn();

      expect(await screen.findByText(/Closed: no new topics or replies/)).toBeInTheDocument();
      expect(screen.getByTestId('no-new-topics')).toHaveTextContent(
        'This forum is closed to new topics.'
      );
      expect(screen.queryByRole('link', { name: '+ New Thread' })).not.toBeInTheDocument();
    });

    it('hides the composer link from a member who may not post here', async () => {
      withRow({ capabilities: { ...allowed, can_post: false } });
      renderSignedIn();
      expect(await screen.findByTestId('no-new-topics')).toHaveTextContent(
        'You cannot start topics in this forum.'
      );
      expect(screen.queryByRole('link', { name: '+ New Thread' })).not.toBeInTheDocument();
    });

    it('renders the forum icon and accent colour', async () => {
      withRow({ icon: '🌿', colour: 'bloom', capabilities: allowed });
      renderThreadListPage(['/forum/3-plant-care']);

      await waitFor(() => expect(screen.getByTestId('forum-icon')).toHaveTextContent('🌿'));
      expect(screen.getByTestId('forum-icon').getAttribute('style')).toContain('var(--gt-berry)');
      expect(screen.getByRole('heading', { level: 1 }).getAttribute('style')).toContain(
        'var(--gt-berry)'
      );
    });

    it('applies the forum theme as a token scope', async () => {
      withRow({ theme: 'terracotta', capabilities: allowed });
      renderThreadListPage(['/forum/3-plant-care']);
      await waitFor(() =>
        expect(screen.getByTestId('forum-page')).toHaveAttribute('data-forum-theme', 'terracotta')
      );
      expect(screen.getByTestId('forum-page')).toHaveClass('forum-theme');
    });

    it('applies no theme scope for none or an unknown theme', async () => {
      withRow({ theme: 'neon' as never, capabilities: allowed });
      renderThreadListPage(['/forum/3-plant-care']);
      await screen.findByRole('link', { name: '+ New Thread' });
      expect(screen.getByTestId('forum-page')).not.toHaveAttribute('data-forum-theme');
    });

    it('opens on the forum default sort when the URL names none', async () => {
      withRow({ default_sort: '-created_at', capabilities: allowed });
      renderThreadListPage(['/forum/3-plant-care']);
      await waitFor(() =>
        expect(screen.getByRole('button', { name: 'Newest' })).toHaveAttribute(
          'aria-pressed',
          'true'
        )
      );
      expect(forumService.fetchThreads).toHaveBeenCalledWith(
        expect.objectContaining({ board: 'plant-care', sort: undefined })
      );
    });

    it('offers a signed-in member the watch level picker', async () => {
      withRow({ watch_level: 'tracking', capabilities: allowed });
      renderSignedIn();
      const picker = await screen.findByLabelText('Notifications');
      expect(picker).toHaveValue('tracking');
    });

    it('offers a guest no watch level picker', async () => {
      withRow({ watch_level: null, capabilities: { ...allowed, can_post: false } });
      renderThreadListPage(['/forum/3-plant-care']);
      // A guest keeps the composer link (it leads to sign-in).
      await screen.findByRole('link', { name: '+ New Thread' });
      expect(screen.queryByLabelText('Notifications')).not.toBeInTheDocument();
    });
  });
});
