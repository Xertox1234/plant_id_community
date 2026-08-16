import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import CategoryListPage from './CategoryListPage';
import { resolveBoardFilter } from '../../utils/forumBoardFilter';
import { createMockCategory } from '../../tests/forumUtils';
import type { Category, ForumMyStats, RecentTopic } from '../../types/forum';
import * as forumService from '../../services/forumService';
import * as blogService from '../../services/blogService';
import { useAuth } from '../../contexts/AuthContext';
import { logger } from '../../utils/logger';

// Mock the forumService
vi.mock('../../services/forumService');

// Defensive mock for FromTheBlogModule's rail fetch (brief Step 4). RailSlot
// portals into `#app-rail`, which doesn't exist in jsdom for this suite — so
// the module never actually mounts and this fetch is never called — but the
// mock guards against a real network call if that changes.
vi.mock('../../services/blogService');

vi.mock('../../contexts/AuthContext', () => ({ useAuth: vi.fn() }));

// Mock logger
vi.mock('../../utils/logger', () => ({
  logger: {
    error: vi.fn(),
    warn: vi.fn(),
    info: vi.fn(),
    debug: vi.fn(),
  },
}));

/**
 * The forum home payload: boards plus the CMS welcome copy, in one response
 * (todo 278 L2 — `GET boards/` returns `{results, intro}`).
 */
function indexPayload(categories: Category[], intro = '') {
  return { categories, intro };
}

/**
 * Helper to render CategoryListPage with Router context
 */
function renderCategoryListPage() {
  return render(
    <BrowserRouter>
      <CategoryListPage />
    </BrowserRouter>
  );
}

const mockAuth = (isAuthenticated: boolean) =>
  ({ user: isAuthenticated ? { id: 1 } : null, isAuthenticated }) as unknown as ReturnType<
    typeof useAuth
  >;

function makeRecentTopic(overrides: Partial<RecentTopic> = {}): RecentTopic {
  return {
    id: 1,
    slug: 'watering-tips',
    title: 'Watering tips',
    board: { id: 1, name: 'Plant Care', slug: 'plant-care' },
    reply_count: 3,
    last_post_at: '2026-08-01T00:00:00Z',
    is_pinned: false,
    thumbnail_url: null,
    ...overrides,
  };
}

function makeMyStats(overrides: Partial<ForumMyStats> = {}): ForumMyStats {
  return {
    posts: 12,
    solutions_accepted: 3,
    identifications_shared: 7,
    ...overrides,
  };
}

describe('CategoryListPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Set fresh each test (not chained at module scope): vitest.config.ts's
    // global `mockReset: true` wipes any factory-chained mock value before
    // every test.
    vi.mocked(blogService.fetchPopularPosts).mockResolvedValue([]);
    // Default every test to logged-out + no recent topics; individual tests
    // override either mock to exercise the authed / event-hero paths.
    vi.mocked(useAuth).mockReturnValue(mockAuth(false));
    vi.mocked(forumService.fetchRecentTopics).mockResolvedValue([]);
    // Defensive mock for CommunityExpertsModule's rail fetch (Task 10), same
    // reasoning as the blogService mock above: RailSlot portals into
    // `#app-rail`, which doesn't exist in jsdom for this suite, so the module
    // never actually mounts — but this guards against a real network call
    // (or a thrown TypeError against an auto-mocked `undefined`) if that changes.
    vi.mocked(forumService.fetchExperts).mockResolvedValue([]);
  });

  it('shows loading spinner while fetching categories', () => {
    // Mock API to never resolve (stays in loading state)
    vi.spyOn(forumService, 'fetchForumIndex').mockImplementation(() => new Promise(() => {}));

    renderCategoryListPage();

    // LoadingSpinner should be visible
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('renders categories when API call succeeds', async () => {
    const mockCategories = [
      createMockCategory({
        id: 'cat-1',
        name: 'Plant Care',
        description: 'Tips for plant care',
        thread_count: 50,
        post_count: 300,
      }),
      createMockCategory({
        id: 'cat-2',
        name: 'Plant Identification',
        description: 'Help identify plants',
        thread_count: 75,
        post_count: 500,
      }),
    ];

    vi.spyOn(forumService, 'fetchForumIndex').mockResolvedValue(indexPayload(mockCategories));

    renderCategoryListPage();

    // Board names now also appear as filter-chip labels (both boards share the
    // fixture's default unmapped slug, so their chip label falls back to their
    // own name) — scope to the card heading to disambiguate from the chip.
    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 3, name: 'Plant Care' })).toBeInTheDocument();
    });

    expect(screen.getByText('Tips for plant care')).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { level: 3, name: 'Plant Identification' })
    ).toBeInTheDocument();
    expect(screen.getByText('Help identify plants')).toBeInTheDocument();
  });

  it('renders the hero and an accessible page heading', async () => {
    vi.spyOn(forumService, 'fetchForumIndex').mockResolvedValue(indexPayload([]));

    renderCategoryListPage();

    // HeroCard's title renders as an h2; the page still carries exactly one
    // (sr-only) h1 for the document outline.
    await waitFor(() => {
      expect(screen.getByText('Ask the canopy')).toBeInTheDocument();
    });
    expect(screen.getByRole('heading', { level: 1, name: 'Community forum' })).toBeInTheDocument();
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
    // H9: the route sets a descriptive document title (React 19 metadata).
    expect(document.title).toContain('Community Forum');
  });

  it('displays error message when API call fails', async () => {
    const errorMessage = 'Failed to load categories';

    vi.spyOn(forumService, 'fetchForumIndex').mockRejectedValue(new Error(errorMessage));

    renderCategoryListPage();

    await waitFor(() => {
      expect(screen.getByText(/Error loading categories/i)).toBeInTheDocument();
    });

    expect(screen.getByText(errorMessage)).toBeInTheDocument();
  });

  it('recovers via Retry after a failed load (audit H18)', async () => {
    const fetchSpy = vi
      .spyOn(forumService, 'fetchForumIndex')
      .mockRejectedValueOnce(new Error('Network error'))
      .mockResolvedValueOnce(
        indexPayload([createMockCategory({ id: 'cat-1', name: 'Plant Care' })])
      );

    renderCategoryListPage();

    // First load fails → error panel with a Retry button.
    const retry = await screen.findByRole('button', { name: /retry/i });
    // Retry re-runs the fetch; the second attempt succeeds and renders content.
    await userEvent.click(retry);

    await waitFor(() => expect(screen.getByText('Plant Care')).toBeInTheDocument());
    expect(screen.queryByRole('button', { name: /retry/i })).not.toBeInTheDocument();
    expect(fetchSpy).toHaveBeenCalledTimes(2);
  });

  it('shows empty state when no categories exist', async () => {
    vi.spyOn(forumService, 'fetchForumIndex').mockResolvedValue(indexPayload([]));

    renderCategoryListPage();

    await waitFor(() => {
      expect(screen.getByText('No boards yet')).toBeInTheDocument();
    });

    // Audit L2: the empty state explains what the forum is for and offers a
    // way onward, instead of reading as a broken page.
    expect(screen.getByText(/This community is just getting started/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /identify a plant/i })).toHaveAttribute(
      'href',
      '/identify'
    );
  });

  it('renders the CMS welcome copy as HTML (audit L2)', async () => {
    vi.spyOn(forumService, 'fetchForumIndex').mockResolvedValue(
      indexPayload([], '<p>Welcome! Please read the <a href="/rules">rules</a>.</p>')
    );

    renderCategoryListPage();

    await waitFor(() => expect(screen.getByText(/Welcome!/)).toBeInTheDocument());
    // Rendered as markup, not escaped text — the link is a real anchor.
    expect(screen.getByRole('link', { name: 'rules' })).toHaveAttribute('href', '/rules');
  });

  it('sanitizes the CMS welcome copy before rendering it', async () => {
    vi.spyOn(forumService, 'fetchForumIndex').mockResolvedValue(
      indexPayload(
        [],
        '<p>Hi</p><img src="x" onerror="window.__xss = true">' +
          '<p onclick="window.__xss = true">clickme</p>' +
          '<p><a href="javascript:window.__xss = true">link</a></p>'
      )
    );

    renderCategoryListPage();

    await waitFor(() => expect(screen.getByText('Hi')).toBeInTheDocument());
    // The backend sanitizes too; this is the second layer, and the one that
    // protects against a compromised/mis-implemented first layer.
    // Scoped to `.prose` (the sanitized-intro container) — the page's own
    // hero art is a legitimate `<img>` elsewhere in the DOM, so an unscoped
    // `document.querySelector('img')` would false-fail on that, not on a
    // sanitization gap.
    // `img` at all, not just `img[onerror]` — the narrower assertion would also
    // pass under the FULL preset, which allows images outright, so it would not
    // actually pin STANDARD's "no media".
    expect(document.querySelector('.prose img')).toBeNull();
    // Attribute and URI stripping on tags that ARE allowed.
    expect(document.querySelector('.prose [onclick]')).toBeNull();
    expect(document.querySelector('.prose a[href^="javascript:"]')).toBeNull();
  });

  it('renders no welcome block when the intro sanitizes away to nothing', async () => {
    // Truthy raw string, empty after sanitizing — gating on the raw value
    // would render an empty padded box.
    vi.spyOn(forumService, 'fetchForumIndex').mockResolvedValue(
      indexPayload([], '<img src="x"><script>window.__xss = true</script>')
    );

    renderCategoryListPage();

    await waitFor(() => expect(screen.getByText('No boards yet')).toBeInTheDocument());
    expect(document.querySelector('.prose')).toBeNull();
  });

  it('renders no welcome block when the CMS intro is empty', async () => {
    vi.spyOn(forumService, 'fetchForumIndex').mockResolvedValue(indexPayload([], ''));

    renderCategoryListPage();

    await waitFor(() => expect(screen.getByText('No boards yet')).toBeInTheDocument());
    expect(document.querySelector('.prose')).toBeNull();
  });

  it('calls fetchForumIndex on mount', async () => {
    const fetchSpy = vi.spyOn(forumService, 'fetchForumIndex').mockResolvedValue(indexPayload([]));

    renderCategoryListPage();

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledTimes(1);
    });
  });

  it('renders multiple categories in grid layout', async () => {
    const mockCategories = [
      createMockCategory({ id: 'cat-1', name: 'Category 1' }),
      createMockCategory({ id: 'cat-2', name: 'Category 2' }),
      createMockCategory({ id: 'cat-3', name: 'Category 3' }),
    ];

    vi.spyOn(forumService, 'fetchForumIndex').mockResolvedValue(indexPayload(mockCategories));

    renderCategoryListPage();

    // Scope to the card heading — each board's name also appears as a filter
    // chip's fallback label (unmapped slug), so a bare text query is ambiguous.
    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 3, name: 'Category 1' })).toBeInTheDocument();
    });

    expect(screen.getByRole('heading', { level: 3, name: 'Category 2' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 3, name: 'Category 3' })).toBeInTheDocument();
  });

  it('hides loading spinner after data loads', async () => {
    const mockCategories = [createMockCategory()];

    vi.spyOn(forumService, 'fetchForumIndex').mockResolvedValue(indexPayload(mockCategories));

    renderCategoryListPage();

    // Initially should show loading
    expect(screen.getByRole('status')).toBeInTheDocument();

    // After loading, spinner should be gone
    await waitFor(() => {
      expect(screen.queryByRole('status')).not.toBeInTheDocument();
    });
  });

  it('logs errors to console when API fails', async () => {
    const errorMessage = 'Network error';

    vi.spyOn(forumService, 'fetchForumIndex').mockRejectedValue(new Error(errorMessage));

    renderCategoryListPage();

    await waitFor(() => {
      expect(logger.error).toHaveBeenCalled();
    });

    // Check that error was logged with correct format
    expect(logger.error).toHaveBeenCalledWith(
      'Error loading forum categories',
      expect.objectContaining({
        component: 'CategoryListPage',
        error: expect.any(Error),
      })
    );
  });

  describe('board filter chips', () => {
    // Distinct slugs (createMockCategory defaults them all to 'plant-care')
    // and one real Canopy slug (pests-diseases) so a passing test proves the
    // identity map is wired into the page, not just into the unit test.
    const boards = [
      createMockCategory({ id: 'cat-1', name: 'Pests & Diseases', slug: 'pests-diseases' }),
      createMockCategory({ id: 'cat-2', name: 'Care Problems', slug: 'care-problems' }),
      createMockCategory({ id: 'cat-3', name: 'Random Board', slug: 'random-board' }),
    ];

    // Board-list membership is checked via the card's h3 heading, not a bare
    // text query: the "Random Board" fixture's slug isn't in the identity
    // map, so its chip label falls back to its own name and the chip row
    // isn't affected by the filter — a bare getByText would match both the
    // card and the (still-visible) chip.
    function cardHeading(name: string) {
      return screen.getByRole('heading', { level: 3, name });
    }
    function queryCardHeading(name: string) {
      return screen.queryByRole('heading', { level: 3, name });
    }

    it('renders one chip per board plus an All chip, using the board identity chip label', async () => {
      vi.spyOn(forumService, 'fetchForumIndex').mockResolvedValue(indexPayload(boards));

      renderCategoryListPage();

      await waitFor(() => expect(cardHeading('Pests & Diseases')).toBeInTheDocument());

      const group = screen.getByRole('group', { name: 'Filter boards' });
      const chips = within(group).getAllByRole('button');
      expect(chips).toHaveLength(boards.length + 1);

      expect(within(group).getByRole('button', { name: 'All' })).toBeInTheDocument();
      // pests-diseases maps to the short "Pests" chip label (spec identity map).
      expect(within(group).getByRole('button', { name: 'Pests' })).toBeInTheDocument();
      expect(within(group).getByRole('button', { name: 'Care' })).toBeInTheDocument();
      // Unknown slug falls back to the board's own name.
      expect(within(group).getByRole('button', { name: 'Random Board' })).toBeInTheDocument();
    });

    it('filters the board list when a chip is clicked, and restores on a second click', async () => {
      vi.spyOn(forumService, 'fetchForumIndex').mockResolvedValue(indexPayload(boards));

      renderCategoryListPage();

      await waitFor(() => expect(cardHeading('Pests & Diseases')).toBeInTheDocument());
      expect(cardHeading('Care Problems')).toBeInTheDocument();
      expect(cardHeading('Random Board')).toBeInTheDocument();

      const group = screen.getByRole('group', { name: 'Filter boards' });
      const pestsChip = within(group).getByRole('button', { name: 'Pests' });

      await userEvent.click(pestsChip);

      expect(pestsChip).toHaveAttribute('aria-pressed', 'true');
      expect(cardHeading('Pests & Diseases')).toBeInTheDocument();
      expect(queryCardHeading('Care Problems')).not.toBeInTheDocument();
      expect(queryCardHeading('Random Board')).not.toBeInTheDocument();

      // Clicking the same chip again clears the filter.
      await userEvent.click(pestsChip);

      expect(pestsChip).toHaveAttribute('aria-pressed', 'false');
      expect(cardHeading('Pests & Diseases')).toBeInTheDocument();
      expect(cardHeading('Care Problems')).toBeInTheDocument();
      expect(cardHeading('Random Board')).toBeInTheDocument();
    });

    it('restores the full list when All is clicked after filtering', async () => {
      vi.spyOn(forumService, 'fetchForumIndex').mockResolvedValue(indexPayload(boards));

      renderCategoryListPage();

      await waitFor(() => expect(cardHeading('Pests & Diseases')).toBeInTheDocument());

      const group = screen.getByRole('group', { name: 'Filter boards' });
      await userEvent.click(within(group).getByRole('button', { name: 'Care' }));
      expect(queryCardHeading('Pests & Diseases')).not.toBeInTheDocument();

      const allChip = within(group).getByRole('button', { name: 'All' });
      await userEvent.click(allChip);

      expect(allChip).toHaveAttribute('aria-pressed', 'true');
      expect(cardHeading('Pests & Diseases')).toBeInTheDocument();
      expect(cardHeading('Care Problems')).toBeInTheDocument();
      expect(cardHeading('Random Board')).toBeInTheDocument();
    });

    it('does not render the chip row for a single board', async () => {
      vi.spyOn(forumService, 'fetchForumIndex').mockResolvedValue(
        indexPayload([createMockCategory({ id: 'cat-1', name: 'Solo Board' })])
      );

      renderCategoryListPage();

      await waitFor(() => expect(screen.getByText('Solo Board')).toBeInTheDocument());
      expect(screen.queryByRole('group', { name: 'Filter boards' })).not.toBeInTheDocument();
    });
  });

  describe('stale activeBoard filter (round-2 review)', () => {
    // resolveBoardFilter() is the derived-state guard behind CategoryListPage's
    // chip filter. The browser-level scenario it exists for — select a chip,
    // then a refetch's payload no longer contains that board's slug — has no
    // reachable trigger in the current app to exercise end-to-end: the only
    // refetch path is ForumErrorState's Retry, which only renders during an
    // *error* state, and that state replaces the entire board/chip section (so
    // there is never a chip to have selected beforehand). See the exported
    // function's doc comment in CategoryListPage.tsx for the full trace.
    //
    // This is a direct unit test of the pure derivation instead: it fails
    // without the fix (a bare `activeBoard ? categories.filter(...) : categories`
    // would return an empty array here, not the full list) and passes with it.
    const boards = [
      createMockCategory({ id: 'cat-1', name: 'Pests & Diseases', slug: 'pests-diseases' }),
      createMockCategory({ id: 'cat-2', name: 'Care Problems', slug: 'care-problems' }),
    ];

    it('falls back to "All" when the selected board is no longer in the fetched list', () => {
      const result = resolveBoardFilter(boards, 'a-board-that-no-longer-exists');

      // The effective selection collapses to null — the same value the "All"
      // chip's `active` prop and every per-board chip's `active` prop both
      // read from, so the chip row and the list agree: nothing but "All" is
      // pressed. Missing slug -> effective selection null, pinned directly.
      expect(result.effectiveBoard).toBeNull();
      // The full, unfiltered list — not a blank/empty array over a real
      // selection nobody can act on anymore.
      expect(result.visibleCategories).toEqual(boards);
    });

    it('still filters normally when the selected board is present', () => {
      const result = resolveBoardFilter(boards, 'care-problems');

      expect(result.effectiveBoard).toBe('care-problems');
      expect(result.visibleCategories).toEqual([boards[1]]);
    });

    it('shows all boards when no filter is selected', () => {
      const result = resolveBoardFilter(boards, null);

      expect(result.effectiveBoard).toBeNull();
      expect(result.visibleCategories).toEqual(boards);
    });
  });

  describe('bloom watch event hero', () => {
    it('fetches the server MAX recent-topics window, not just the rail display count', async () => {
      // RECENT_TOPICS_MAX_LIMIT (wagtail_forum/conf.py) is 20 — the hero
      // scans the FULL fetched array for the pinned bloom-watch topic, so a
      // narrower fetch lets newer topics evict a still-live pinned event
      // out of the window mid-event (review finding #6).
      vi.spyOn(forumService, 'fetchForumIndex').mockResolvedValue(indexPayload([]));
      renderCategoryListPage();

      await waitFor(() => expect(forumService.fetchRecentTopics).toHaveBeenCalledWith(20));
    });

    it("still shows the event hero when the pinned bloom-watch topic sits past the rail's 3-item display cap but within the fetched window", async () => {
      vi.spyOn(forumService, 'fetchForumIndex').mockResolvedValue(indexPayload([]));
      const bloomWatch = makeRecentTopic({
        id: 42,
        slug: 'bloom-watch-2026',
        title: 'Bloom Watch 2026',
        board: { id: 7, name: 'Showcase', slug: 'showcase' },
        is_pinned: true,
      });
      // 6 newer, unrelated topics ahead of the pinned event — more than the
      // rail's RAIL_TOPIC_LIMIT (3) AND more than the old, buggy fetch
      // count (5). The mock mirrors the real endpoint's `?limit=` truncation
      // (newest-first, pinned event last) so this test exercises the ACTUAL
      // regression: it only passes when the page requests a window wide
      // enough that the truncated response still contains the pinned topic
      // — a plain `mockResolvedValue` ignoring the call arg would pass even
      // under the `fetchRecentTopics(5)` mutation.
      const newerTopics = Array.from({ length: 6 }, (_, i) =>
        makeRecentTopic({ id: i + 1, slug: `newer-topic-${i + 1}` })
      );
      const fullWindow = [...newerTopics, bloomWatch];
      vi.mocked(forumService.fetchRecentTopics).mockImplementation((limit = 5) =>
        Promise.resolve(fullWindow.slice(0, limit))
      );

      renderCategoryListPage();

      const cta = await screen.findByRole('link', { name: 'Join the bloom watch' });
      expect(cta).toHaveAttribute('href', '/forum/7-showcase/42-bloom-watch-2026');
      expect(screen.queryByText('Ask the canopy')).not.toBeInTheDocument();
    });

    it('renders the event hero, linking to the topic path, when a pinned bloom-watch topic is in the recent feed', async () => {
      vi.spyOn(forumService, 'fetchForumIndex').mockResolvedValue(indexPayload([]));
      const bloomWatch = makeRecentTopic({
        id: 42,
        slug: 'bloom-watch-2026',
        title: 'Bloom Watch 2026',
        board: { id: 7, name: 'Showcase', slug: 'showcase' },
        is_pinned: true,
      });
      vi.mocked(forumService.fetchRecentTopics).mockResolvedValue([bloomWatch]);

      renderCategoryListPage();

      const cta = await screen.findByRole('link', { name: 'Join the bloom watch' });
      expect(cta).toHaveAttribute('href', '/forum/7-showcase/42-bloom-watch-2026');
      expect(screen.getByText('The bloom watch is on.')).toBeInTheDocument();
      expect(screen.queryByText('Ask the canopy')).not.toBeInTheDocument();
    });

    it('keeps the "Ask the canopy" hero when no pinned bloom-watch topic is present', async () => {
      vi.spyOn(forumService, 'fetchForumIndex').mockResolvedValue(indexPayload([]));
      vi.mocked(forumService.fetchRecentTopics).mockResolvedValue([
        makeRecentTopic({ is_pinned: false }),
        makeRecentTopic({ id: 2, slug: 'unrelated-pinned', is_pinned: true }),
        // is_pinned: false with a matching slug — exercises the other half of
        // the `is_pinned && slug.startsWith(...)` AND, not just is_pinned's.
        makeRecentTopic({ id: 3, slug: 'bloom-watch-2025', is_pinned: false }),
      ]);

      renderCategoryListPage();

      await waitFor(() => expect(screen.getByText('Ask the canopy')).toBeInTheDocument());
      expect(screen.queryByRole('link', { name: 'Join the bloom watch' })).not.toBeInTheDocument();
    });

    it('keeps the "Ask the canopy" hero when fetchRecentTopics rejects', async () => {
      vi.spyOn(forumService, 'fetchForumIndex').mockResolvedValue(indexPayload([]));
      vi.mocked(forumService.fetchRecentTopics).mockRejectedValue(new Error('network error'));

      renderCategoryListPage();

      await waitFor(() => expect(screen.getByText('Ask the canopy')).toBeInTheDocument());
      expect(screen.queryByRole('link', { name: 'Join the bloom watch' })).not.toBeInTheDocument();
    });
  });

  describe('Your season stat cards', () => {
    it('renders four "Your season" cards with real values when authenticated and stats load', async () => {
      vi.spyOn(forumService, 'fetchForumIndex').mockResolvedValue(indexPayload([]));
      vi.mocked(useAuth).mockReturnValue(mockAuth(true));
      vi.mocked(forumService.fetchMyStats).mockResolvedValue(makeMyStats());

      renderCategoryListPage();

      await waitFor(() =>
        expect(screen.getByRole('heading', { name: 'Your season' })).toBeInTheDocument()
      );
      // Each StatCard's label div is a sibling of its value div under one
      // shared wrapper (StatCard.tsx) — scoping to that wrapper via `within`
      // proves each VALUE belongs to its own label, not just that every
      // number and every label exist somewhere on the page.
      const statCard = (label: string) => screen.getByText(label).parentElement as HTMLElement;
      expect(within(statCard('Identifications')).getByText('7')).toBeInTheDocument();
      expect(within(statCard('Posts')).getByText('12')).toBeInTheDocument();
      expect(within(statCard('Solutions')).getByText('3')).toBeInTheDocument();
      expect(within(statCard('Day streak')).getByText('—')).toBeInTheDocument();
      expect(within(statCard('Day streak')).getByText('Coming soon')).toBeInTheDocument();
      // The trio is fully replaced, not shown alongside the four cards.
      expect(screen.queryByText('Threads')).not.toBeInTheDocument();
    });

    it('shows the original trio and no "Your season" heading when anonymous', async () => {
      vi.spyOn(forumService, 'fetchForumIndex').mockResolvedValue(
        indexPayload([createMockCategory({ id: 'cat-1', name: 'Plant Care' })])
      );

      renderCategoryListPage();

      await waitFor(() => expect(screen.getByText('Threads')).toBeInTheDocument());
      expect(screen.getByText('Posts')).toBeInTheDocument();
      expect(screen.queryByRole('heading', { name: 'Your season' })).not.toBeInTheDocument();
      expect(forumService.fetchMyStats).not.toHaveBeenCalled();
    });

    it('hides the stats row (trio absent, no crash) when the authed stats fetch rejects', async () => {
      vi.spyOn(forumService, 'fetchForumIndex').mockResolvedValue(
        indexPayload([createMockCategory({ id: 'cat-1', name: 'Plant Care' })])
      );
      vi.mocked(useAuth).mockReturnValue(mockAuth(true));
      vi.mocked(forumService.fetchMyStats).mockRejectedValue(new Error('network error'));

      renderCategoryListPage();

      // Page still renders fine: hero and boards are present.
      await waitFor(() => expect(screen.getByText('Ask the canopy')).toBeInTheDocument());
      expect(screen.getByRole('heading', { level: 3, name: 'Plant Care' })).toBeInTheDocument();
      expect(screen.queryByRole('heading', { name: 'Your season' })).not.toBeInTheDocument();
      expect(screen.queryByText('Threads')).not.toBeInTheDocument();
    });
  });
});
