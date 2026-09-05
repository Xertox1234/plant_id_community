import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, within, act, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import * as ReactRouter from 'react-router-dom';
import ThreadDetailPage, { NEW_REPLIES_POLL_INTERVAL_MS } from './ThreadDetailPage';
import { createMockThread, createMockPost } from '../../tests/forumUtils';
import * as forumService from '../../services/forumService';
import * as blogService from '../../services/blogService';
import { useAuth } from '../../contexts/AuthContext';
import { AnnouncerProvider } from '../../contexts/AnnouncerContext';
import { htmlToBodyBlocks } from '../../utils/forumBody';
import { logger } from '../../utils/logger';

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useParams: vi.fn(),
  };
});

// Mock the forumService; stub TipTapEditor to a textarea (jsdom-hostile rich editor).
// The aria-label is the placeholder so the reply composer ("Write a reply...") and
// the edit editor ("body", no placeholder) are individually addressable.
// `content` rides through as defaultValue so what the page PUTS INTO the
// editor (a loaded edit body, a Quote insert — todo 342) is observable; a stub
// that dropped it would show an empty field whatever the page did.
vi.mock('../../services/forumService');
// Defensive mock for FromTheBlogModule's rail fetch and the page's own
// "more in this board" rail fetch. Neither fires here: the setup.ts
// matchMedia polyfill reports the xl rail query unmatched, so RailSlot
// mounts nothing and the board fetch is skipped (and `#app-rail` doesn't
// exist in jsdom anyway) — but both mocks guard against a real network call.
vi.mock('../../services/blogService');
vi.mock('../../contexts/AuthContext', () => ({ useAuth: vi.fn() }));
vi.mock('../../components/forum/TipTapEditor', () => ({
  default: ({
    content,
    onChange,
    placeholder,
  }: {
    content?: string;
    onChange?: (html: string) => void;
    placeholder?: string;
  }) => (
    <textarea
      aria-label={placeholder || 'body'}
      defaultValue={content}
      onChange={(e) => onChange?.(`<p>${e.target.value}</p>`)}
    />
  ),
}));

/**
 * Helper to render ThreadDetailPage with Router
 */
function renderThreadDetailPage(categorySlug = 'plant-care', threadSlug = 'watering-tips') {
  return render(
    <MemoryRouter initialEntries={[`/forum/${categorySlug}/${threadSlug}`]}>
      <AnnouncerProvider>
        <ThreadDetailPage />
      </AnnouncerProvider>
    </MemoryRouter>
  );
}

const mockAuth = (isAuthenticated: boolean) =>
  ({
    user: isAuthenticated ? { id: 1 } : null,
    isAuthenticated,
    // Defense-in-depth (todo 297): handleReply calls this after every reply
    // (published or pending). Resolving to the SAME identity `user` above
    // means no drift is detected, preserving every existing test's
    // success-path assertions.
    revalidateIdentity: vi.fn().mockResolvedValue(isAuthenticated ? { id: 1 } : null),
  }) as unknown as ReturnType<typeof useAuth>;

describe('ThreadDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();

    // Mock useParams to return hybrid id-slug params; lookups use the leading id.
    vi.mocked(ReactRouter.useParams).mockReturnValue({
      categorySlug: '3-plant-care',
      threadSlug: '12-watering-tips',
    });
    // Default to authenticated so the write UI renders; the logged-out test overrides.
    vi.mocked(useAuth).mockReturnValue(mockAuth(true));
    // The rail's "more in this board" fetch and FromTheBlogModule's popular-posts
    // fetch. Set fresh each test (not chained at module scope): vitest.config.ts's
    // global `mockReset: true` wipes any factory-chained mock value before every test.
    vi.mocked(forumService.fetchThreads).mockResolvedValue({
      items: [],
      meta: { next: null, count: 0 },
    });
    vi.mocked(blogService.fetchPopularPosts).mockResolvedValue([]);
  });

  it('shows error (not infinite spinner) when threadSlug has no leading id', async () => {
    vi.mocked(ReactRouter.useParams).mockReturnValue({
      categorySlug: '3-plant-care',
      threadSlug: 'no-id-here',
    });

    renderThreadDetailPage();

    await waitFor(() => {
      expect(screen.getByText(/Invalid thread URL/i)).toBeInTheDocument();
    });
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });

  it('shows loading spinner while fetching data', () => {
    vi.spyOn(forumService, 'fetchThread').mockImplementation(() => new Promise(() => {}));
    vi.spyOn(forumService, 'fetchPosts').mockImplementation(() => new Promise(() => {}));

    renderThreadDetailPage();

    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('fetches thread and posts on mount', async () => {
    const mockThread = createMockThread({ slug: 'watering-tips' });
    const mockPosts = {
      items: [createMockPost({ id: '1' })],
      meta: { count: 0, next: null, previous: null },
    };

    const fetchThreadSpy = vi.spyOn(forumService, 'fetchThread').mockResolvedValue(mockThread);
    const fetchPostsSpy = vi.spyOn(forumService, 'fetchPosts').mockResolvedValue(mockPosts);

    renderThreadDetailPage();

    await waitFor(() => {
      expect(fetchThreadSpy).toHaveBeenCalledWith(12);
      expect(fetchPostsSpy).toHaveBeenCalledWith({ thread: 12 });
    });
  });

  it('displays thread title and metadata', async () => {
    const mockThread = createMockThread({
      slug: 'watering-tips',
      title: 'How to water succulents?',
      author: {
        username: 'gardener',
        display_name: 'Master Gardener',
        avatar: null,
        trust_level: null,
      },
      view_count: 150,
    });

    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(mockThread);
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue({
      items: [],
      meta: { count: 0 },
    });

    renderThreadDetailPage();

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { level: 1, name: 'How to water succulents?' })
      ).toBeInTheDocument();
    });

    expect(screen.getByText(/Master Gardener/i)).toBeInTheDocument();
    // The header author name links to their public profile (todo 257 H7).
    expect(screen.getByRole('link', { name: 'Master Gardener' })).toHaveAttribute(
      'href',
      '/forum/users/gardener'
    );
    expect(screen.getByText(/150 views/i)).toBeInTheDocument();
    // H9: descriptive title + shareable OG tags (React 19 metadata).
    expect(document.title).toContain('How to water succulents?');
    expect(document.querySelector('meta[property="og:type"]')?.getAttribute('content')).toBe(
      'article'
    );
    expect(document.querySelector('meta[property="og:url"]')?.getAttribute('content')).toBe(
      window.location.origin + window.location.pathname
    );
    expect(
      document.querySelector('meta[property="og:description"]')?.getAttribute('content')
    ).toContain('discussion');
  });

  it('renders breadcrumb navigation', async () => {
    const mockThread = createMockThread({
      slug: 'watering-tips',
      category: {
        id: 'cat-1',
        name: 'Plant Care',
        slug: 'plant-care',
        icon: '🌱',
        created_at: '2025-01-01T00:00:00Z',
      },
    });

    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(mockThread);
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue({
      items: [],
      meta: { count: 0 },
    });

    renderThreadDetailPage();

    await waitFor(() => {
      expect(screen.getByLabelText('Breadcrumb')).toBeInTheDocument();
    });

    const breadcrumb = screen.getByLabelText('Breadcrumb');
    expect(breadcrumb).toHaveTextContent('Forum');
    expect(breadcrumb).toHaveTextContent('Plant Care');
  });

  it('displays pinned badge when thread is pinned', async () => {
    const mockThread = createMockThread({ is_pinned: true });

    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(mockThread);
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue({
      items: [],
      meta: { count: 0 },
    });

    renderThreadDetailPage();

    await waitFor(() => {
      expect(screen.getByText(/pinned/i)).toBeInTheDocument();
    });
  });

  it('displays locked badge when thread is locked', async () => {
    const mockThread = createMockThread({ is_locked: true });

    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(mockThread);
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue({
      items: [],
      meta: { count: 0 },
    });

    renderThreadDetailPage();

    await waitFor(() => {
      expect(screen.getByText(/^locked$/i)).toBeInTheDocument();
    });
  });

  it('renders posts when API call succeeds', async () => {
    const mockThread = createMockThread();
    const mockPosts = {
      items: [
        createMockPost({
          id: '1',
          body: [{ id: 'b1', type: 'paragraph', value: '<p>First post content</p>' }],
          is_first_post: true,
        }),
        createMockPost({
          id: '2',
          body: [{ id: 'b2', type: 'paragraph', value: '<p>Second post content</p>' }],
          is_first_post: false,
        }),
      ],
      meta: { count: 0, next: null, previous: null },
    };

    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(mockThread);
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue(mockPosts);

    renderThreadDetailPage();

    await waitFor(() => {
      expect(screen.getByText('First post content')).toBeInTheDocument();
    });

    expect(screen.getByText('Second post content')).toBeInTheDocument();
  });

  it('displays error message when thread fetch fails', async () => {
    const errorMessage = 'Thread not found';

    vi.spyOn(forumService, 'fetchThread').mockRejectedValue(new Error(errorMessage));
    vi.spyOn(forumService, 'fetchPosts').mockRejectedValue(new Error(errorMessage));

    renderThreadDetailPage();

    await waitFor(() => {
      expect(screen.getByText(/Error:/i)).toBeInTheDocument();
    });

    expect(screen.getByText(errorMessage)).toBeInTheDocument();
  });

  it('shows a reply composer (no read-only notice)', async () => {
    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(createMockThread());
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue({ items: [], meta: { count: 0 } });

    renderThreadDetailPage();

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /Post a Reply/i })).toBeInTheDocument();
    });
    expect(screen.getByLabelText('Write a reply...')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Post Reply/i })).toBeInTheDocument();
    expect(screen.queryByText(/coming soon/i)).not.toBeInTheDocument();
  });

  it('hides the reply composer when the thread is locked', async () => {
    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(createMockThread({ is_locked: true }));
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue({ items: [], meta: { count: 0 } });

    renderThreadDetailPage();

    await waitFor(() => {
      expect(screen.getByText(/new replies are disabled/i)).toBeInTheDocument();
    });
    expect(screen.queryByRole('button', { name: /Post Reply/i })).not.toBeInTheDocument();
  });

  it('hides the composer and reaction buttons for a logged-out user', async () => {
    vi.mocked(useAuth).mockReturnValue(mockAuth(false));
    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(createMockThread());
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue({
      items: [createMockPost({ id: '5', reaction_counts: { like: 1 } })],
      meta: { count: 0, next: null, previous: null },
    });

    renderThreadDetailPage();

    await screen.findByText(/Log in/i);
    expect(screen.queryByRole('button', { name: /Post Reply/i })).not.toBeInTheDocument();
    expect(screen.queryByLabelText('React like')).not.toBeInTheDocument();
  });

  it('shows a Follow button for an authenticated user on an unsubscribed thread', async () => {
    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(
      createMockThread({ is_subscribed: false })
    );
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue({ items: [], meta: { count: 0 } });

    renderThreadDetailPage();

    expect(await screen.findByRole('button', { name: /^follow$/i })).toBeInTheDocument();
  });

  it('shows a Following button for an authenticated user on a subscribed thread', async () => {
    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(
      createMockThread({ is_subscribed: true })
    );
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue({ items: [], meta: { count: 0 } });

    renderThreadDetailPage();

    expect(await screen.findByRole('button', { name: /^following$/i })).toBeInTheDocument();
  });

  it('hides the Follow button for a logged-out user', async () => {
    vi.mocked(useAuth).mockReturnValue(mockAuth(false));
    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(
      createMockThread({ is_subscribed: false })
    );
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue({ items: [], meta: { count: 0 } });

    renderThreadDetailPage();

    await screen.findByText(/Log in/i);
    expect(screen.queryByRole('button', { name: /Follow/i })).not.toBeInTheDocument();
  });

  it('clicking Follow subscribes and flips the button to Following', async () => {
    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(
      createMockThread({ is_subscribed: false })
    );
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue({ items: [], meta: { count: 0 } });
    const subscribeSpy = vi.spyOn(forumService, 'subscribeToTopic').mockResolvedValue(undefined);

    renderThreadDetailPage();

    await userEvent.click(await screen.findByRole('button', { name: /^follow$/i }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /^following$/i })).toBeInTheDocument();
    });
    expect(subscribeSpy).toHaveBeenCalledWith(12);
  });

  it('clicking Following unsubscribes and flips the button back to Follow', async () => {
    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(
      createMockThread({ is_subscribed: true })
    );
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue({ items: [], meta: { count: 0 } });
    const unsubscribeSpy = vi
      .spyOn(forumService, 'unsubscribeFromTopic')
      .mockResolvedValue(undefined);

    renderThreadDetailPage();

    await userEvent.click(await screen.findByRole('button', { name: /^following$/i }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /^follow$/i })).toBeInTheDocument();
    });
    expect(unsubscribeSpy).toHaveBeenCalledWith(12);
  });

  it('shows a Bookmark button for an authenticated user on a non-bookmarked thread', async () => {
    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(
      createMockThread({ is_bookmarked: false })
    );
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue({ items: [], meta: { count: 0 } });

    renderThreadDetailPage();

    expect(await screen.findByRole('button', { name: /^bookmark$/i })).toBeInTheDocument();
  });

  it('clicking Bookmark bookmarks and flips the button to Bookmarked', async () => {
    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(
      createMockThread({ is_bookmarked: false })
    );
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue({ items: [], meta: { count: 0 } });
    const bookmarkSpy = vi.spyOn(forumService, 'bookmarkTopic').mockResolvedValue(undefined);

    renderThreadDetailPage();

    await userEvent.click(await screen.findByRole('button', { name: /^bookmark$/i }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /^bookmarked$/i })).toBeInTheDocument();
    });
    expect(bookmarkSpy).toHaveBeenCalledWith(12);
  });

  it('clicking Bookmarked unbookmarks and flips the button back to Bookmark', async () => {
    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(
      createMockThread({ is_bookmarked: true })
    );
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue({ items: [], meta: { count: 0 } });
    const unbookmarkSpy = vi.spyOn(forumService, 'unbookmarkTopic').mockResolvedValue(undefined);

    renderThreadDetailPage();

    await userEvent.click(await screen.findByRole('button', { name: /^bookmarked$/i }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /^bookmark$/i })).toBeInTheDocument();
    });
    expect(unbookmarkSpy).toHaveBeenCalledWith(12);
  });

  it('rolls back the optimistic Bookmark toggle and shows a notice when the request fails', async () => {
    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(
      createMockThread({ is_bookmarked: false })
    );
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue({ items: [], meta: { count: 0 } });
    vi.spyOn(forumService, 'bookmarkTopic').mockRejectedValue(new Error('Network error'));

    renderThreadDetailPage();

    await userEvent.click(await screen.findByRole('button', { name: /^bookmark$/i }));

    await screen.findByText('Network error');
    expect(screen.getByRole('button', { name: /^bookmark$/i })).toBeInTheDocument();
  });

  it('renders the thread poll and votes through the topic id', async () => {
    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(
      createMockThread({
        poll: {
          id: 5,
          question: 'Best soil?',
          closes_at: null,
          is_closed: false,
          max_choices: 1,
          options: [
            { id: 10, text: 'Peat', order: 0, vote_count: 0 },
            { id: 11, text: 'Coir', order: 1, vote_count: 0 },
          ],
          total_votes: 0,
          my_vote_option_ids: [],
        },
      })
    );
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue({ items: [], meta: { count: 0 } });
    const voteSpy = vi.spyOn(forumService, 'votePoll').mockResolvedValue({
      id: 5,
      question: 'Best soil?',
      closes_at: null,
      is_closed: false,
      max_choices: 1,
      options: [
        { id: 10, text: 'Peat', order: 0, vote_count: 1 },
        { id: 11, text: 'Coir', order: 1, vote_count: 0 },
      ],
      total_votes: 1,
      my_vote_option_ids: [10],
    });

    renderThreadDetailPage();

    await userEvent.click(await screen.findByRole('button', { name: 'Peat' }));

    // Voted with the TOPIC id (12 from useParams), not the poll id.
    expect(voteSpy).toHaveBeenCalledWith(12, [10]);
    expect(await screen.findByText('1 (100%)')).toBeInTheDocument();
  });

  it('renders no poll section when the thread has none', async () => {
    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(createMockThread({ poll: null }));
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue({ items: [], meta: { count: 0 } });

    renderThreadDetailPage();

    await screen.findByRole('heading', { level: 1 });
    expect(screen.queryByRole('button', { name: 'Peat' })).not.toBeInTheDocument();
  });

  it('rolls back the optimistic Follow toggle and shows a notice when the request fails', async () => {
    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(
      createMockThread({ is_subscribed: false })
    );
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue({ items: [], meta: { count: 0 } });
    vi.spyOn(forumService, 'subscribeToTopic').mockRejectedValue(new Error('Network error'));

    renderThreadDetailPage();

    await userEvent.click(await screen.findByRole('button', { name: /^follow$/i }));

    await screen.findByText('Network error');
    expect(screen.getByRole('button', { name: /^follow$/i })).toBeInTheDocument();
  });

  it('does not leave the Follow button stuck loading after navigating to a different thread mid-request', async () => {
    const threadA = createMockThread({ is_subscribed: false });
    const threadB = createMockThread({ is_subscribed: false });
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue({ items: [], meta: { count: 0 } });
    const fetchThreadSpy = vi
      .spyOn(forumService, 'fetchThread')
      .mockResolvedValueOnce(threadA)
      .mockResolvedValueOnce(threadB);
    // Thread A's request never settles in this test — simulates navigating
    // away before a slow subscribe request resolves.
    vi.spyOn(forumService, 'subscribeToTopic').mockReturnValue(new Promise(() => {}));

    const { rerender } = renderThreadDetailPage();

    await userEvent.click(await screen.findByRole('button', { name: /^follow$/i }));
    expect(screen.getByRole('button', { name: /^following$/i })).toBeDisabled();

    vi.mocked(ReactRouter.useParams).mockReturnValue({
      categorySlug: '3-plant-care',
      threadSlug: '34-different-thread',
    });
    rerender(
      <MemoryRouter initialEntries={['/forum/plant-care/34-different-thread']}>
        <AnnouncerProvider>
          <ThreadDetailPage />
        </AnnouncerProvider>
      </MemoryRouter>
    );

    await waitFor(() => expect(fetchThreadSpy).toHaveBeenCalledWith(34));
    expect(await screen.findByRole('button', { name: /^follow$/i })).not.toBeDisabled();
  });

  it('a stale request failing after navigating away does not corrupt the new thread state', async () => {
    const threadA = createMockThread({ is_subscribed: false });
    const threadB = createMockThread({ is_subscribed: false });
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue({ items: [], meta: { count: 0 } });
    const fetchThreadSpy = vi
      .spyOn(forumService, 'fetchThread')
      .mockResolvedValueOnce(threadA)
      .mockResolvedValueOnce(threadB);

    let rejectSubscribe!: (err: Error) => void;
    vi.spyOn(forumService, 'subscribeToTopic').mockReturnValue(
      new Promise((_resolve, reject) => {
        rejectSubscribe = reject;
      })
    );
    const loggerErrorSpy = vi.spyOn(logger, 'error').mockImplementation(() => {});

    const { rerender } = renderThreadDetailPage();

    await userEvent.click(await screen.findByRole('button', { name: /^follow$/i }));
    expect(screen.getByRole('button', { name: /^following$/i })).toBeInTheDocument();

    vi.mocked(ReactRouter.useParams).mockReturnValue({
      categorySlug: '3-plant-care',
      threadSlug: '34-different-thread',
    });
    rerender(
      <MemoryRouter initialEntries={['/forum/plant-care/34-different-thread']}>
        <AnnouncerProvider>
          <ThreadDetailPage />
        </AnnouncerProvider>
      </MemoryRouter>
    );
    await waitFor(() => expect(fetchThreadSpy).toHaveBeenCalledWith(34));
    expect(await screen.findByRole('button', { name: /^follow$/i })).toBeInTheDocument();

    // Thread A's request now fails — must not touch thread B's displayed state.
    rejectSubscribe(new Error('Network error'));
    await waitFor(() => expect(loggerErrorSpy).toHaveBeenCalled());

    expect(screen.getByRole('button', { name: /^follow$/i })).toBeInTheDocument();
    expect(screen.queryByText('Network error')).not.toBeInTheDocument();
  });

  it('a reply that resolves after navigating to a different thread does not replace that thread (audit M2)', async () => {
    const threadA = createMockThread({ id: '12', slug: 'watering-tips' });
    const threadB = createMockThread({ id: '34', slug: 'different-thread' });
    const fetchThreadSpy = vi
      .spyOn(forumService, 'fetchThread')
      .mockResolvedValueOnce(threadA)
      .mockResolvedValueOnce(threadB);
    const page = (id: string, text: string) => ({
      items: [
        createMockPost({
          id,
          body: [{ id: `b${id}`, type: 'paragraph', value: `<p>${text}</p>` }],
        }),
      ],
      meta: { count: 1, next: null, previous: null },
    });
    vi.spyOn(forumService, 'fetchPosts').mockImplementation(async ({ thread }) =>
      thread === 34 ? page('7', 'thread B post') : page('8', 'thread A post')
    );
    let resolveCreate!: (value: { id: string; status: 'published' }) => void;
    vi.spyOn(forumService, 'createPost').mockReturnValue(
      new Promise((resolve) => {
        resolveCreate = resolve;
      })
    );

    const auth = mockAuth(true);
    vi.mocked(useAuth).mockReturnValue(auth);

    const { rerender } = renderThreadDetailPage();
    await screen.findByText('thread A post');
    await userEvent.type(screen.getByLabelText('Write a reply...'), 'a reply on A');
    await userEvent.click(screen.getByRole('button', { name: /post reply/i }));

    vi.mocked(ReactRouter.useParams).mockReturnValue({
      categorySlug: '3-plant-care',
      threadSlug: '34-different-thread',
    });
    rerender(
      <MemoryRouter initialEntries={['/forum/plant-care/34-different-thread']}>
        <AnnouncerProvider>
          <ThreadDetailPage />
        </AnnouncerProvider>
      </MemoryRouter>
    );
    await waitFor(() => expect(fetchThreadSpy).toHaveBeenCalledWith(34));
    await screen.findByText('thread B post');

    // Thread A's reply now lands. Without the guard this re-collected thread
    // A's posts into thread B's list and announced success on the wrong page.
    await act(async () => {
      resolveCreate({ id: '99', status: 'published' });
      await new Promise((resolve) => setTimeout(resolve, 20));
    });

    expect(screen.getByText('thread B post')).toBeInTheDocument();
    expect(screen.queryByText('thread A post')).not.toBeInTheDocument();
    expect(document.querySelector('[data-announcer="polite"]')).not.toHaveTextContent(
      'Reply posted.'
    );
    // The todo-297 write-time identity refresh is not skipped by the guard —
    // it touches only AuthContext (code review round 2, PR #629).
    expect(auth.revalidateIdentity).toHaveBeenCalledTimes(1);
  });

  it('a drifted identity is still announced when the reply lands after navigating away', async () => {
    vi.spyOn(forumService, 'fetchThread')
      .mockResolvedValueOnce(createMockThread({ id: '12', slug: 'watering-tips' }))
      .mockResolvedValueOnce(createMockThread({ id: '34', slug: 'different-thread' }));
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue({
      items: [],
      meta: { count: 0, next: null, previous: null },
    });
    let resolveCreate!: (value: { id: string; status: 'published' }) => void;
    vi.spyOn(forumService, 'createPost').mockReturnValue(
      new Promise((resolve) => {
        resolveCreate = resolve;
      })
    );
    vi.mocked(useAuth).mockReturnValue({
      isAuthenticated: true,
      user: { id: 1, username: 'test-user' },
      revalidateIdentity: vi.fn().mockResolvedValue({ id: 2, username: 'someone-else' }),
    } as unknown as ReturnType<typeof useAuth>);

    const { rerender } = renderThreadDetailPage();
    await userEvent.type(await screen.findByLabelText('Write a reply...'), 'a reply on A');
    await userEvent.click(screen.getByRole('button', { name: /post reply/i }));
    vi.mocked(ReactRouter.useParams).mockReturnValue({
      categorySlug: '3-plant-care',
      threadSlug: '34-different-thread',
    });
    rerender(
      <MemoryRouter initialEntries={['/forum/plant-care/34-different-thread']}>
        <AnnouncerProvider>
          <ThreadDetailPage />
        </AnnouncerProvider>
      </MemoryRouter>
    );
    await waitFor(() => expect(forumService.fetchThread).toHaveBeenCalledWith(34));

    await act(async () => {
      resolveCreate({ id: '99', status: 'published' });
      await new Promise((resolve) => setTimeout(resolve, 20));
    });

    // No page-state write for thread A, but the drift reaches the app-global
    // announcer instead of being lost with the navigation.
    expect(document.querySelector('[data-announcer="assertive"]')).toHaveTextContent(
      /posted as someone-else/i
    );
    // …and only there: no notice banner was written onto thread B's page.
    expect(screen.getAllByText(/posted as someone-else/i)).toHaveLength(1);
  });

  it('a passive account swap empties the reply composer and its stored draft (code review, L4)', async () => {
    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(createMockThread());
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue({
      items: [],
      meta: { count: 0, next: null, previous: null },
    });
    vi.mocked(useAuth).mockReturnValue(mockAuth(true));

    const { rerender } = renderThreadDetailPage();
    await userEvent.type(await screen.findByLabelText('Write a reply...'), 'account A, unsent');
    expect(sessionStorage.getItem('forum-draft:reply:12')).toContain('account A, unsent');

    // A focus revalidation found another account's cookie: same page, new user.
    vi.mocked(useAuth).mockReturnValue({
      ...mockAuth(true),
      user: { id: 2 },
    } as unknown as ReturnType<typeof useAuth>);
    rerender(
      <MemoryRouter initialEntries={['/forum/plant-care/watering-tips']}>
        <AnnouncerProvider>
          <ThreadDetailPage />
        </AnnouncerProvider>
      </MemoryRouter>
    );

    await waitFor(() => expect(screen.getByLabelText('Write a reply...')).toHaveValue(''));
    expect(sessionStorage.getItem('forum-draft:reply:12')).toBeNull();
  });

  it('does not leave the Bookmark button stuck loading after navigating to a different thread mid-request', async () => {
    const threadA = createMockThread({ is_bookmarked: false });
    const threadB = createMockThread({ is_bookmarked: false });
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue({ items: [], meta: { count: 0 } });
    const fetchThreadSpy = vi
      .spyOn(forumService, 'fetchThread')
      .mockResolvedValueOnce(threadA)
      .mockResolvedValueOnce(threadB);
    // Thread A's request never settles in this test — simulates navigating
    // away before a slow bookmark request resolves.
    vi.spyOn(forumService, 'bookmarkTopic').mockReturnValue(new Promise(() => {}));

    const { rerender } = renderThreadDetailPage();

    await userEvent.click(await screen.findByRole('button', { name: /^bookmark$/i }));
    expect(screen.getByRole('button', { name: /^bookmarked$/i })).toBeDisabled();

    vi.mocked(ReactRouter.useParams).mockReturnValue({
      categorySlug: '3-plant-care',
      threadSlug: '34-different-thread',
    });
    rerender(
      <MemoryRouter initialEntries={['/forum/plant-care/34-different-thread']}>
        <AnnouncerProvider>
          <ThreadDetailPage />
        </AnnouncerProvider>
      </MemoryRouter>
    );

    await waitFor(() => expect(fetchThreadSpy).toHaveBeenCalledWith(34));
    expect(await screen.findByRole('button', { name: /^bookmark$/i })).not.toBeDisabled();
  });

  it('a stale bookmark request failing after navigating away does not corrupt the new thread state', async () => {
    const threadA = createMockThread({ is_bookmarked: false });
    const threadB = createMockThread({ is_bookmarked: false });
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue({ items: [], meta: { count: 0 } });
    const fetchThreadSpy = vi
      .spyOn(forumService, 'fetchThread')
      .mockResolvedValueOnce(threadA)
      .mockResolvedValueOnce(threadB);

    let rejectBookmark!: (err: Error) => void;
    vi.spyOn(forumService, 'bookmarkTopic').mockReturnValue(
      new Promise((_resolve, reject) => {
        rejectBookmark = reject;
      })
    );
    const loggerErrorSpy = vi.spyOn(logger, 'error').mockImplementation(() => {});

    const { rerender } = renderThreadDetailPage();

    await userEvent.click(await screen.findByRole('button', { name: /^bookmark$/i }));
    expect(screen.getByRole('button', { name: /^bookmarked$/i })).toBeInTheDocument();

    vi.mocked(ReactRouter.useParams).mockReturnValue({
      categorySlug: '3-plant-care',
      threadSlug: '34-different-thread',
    });
    rerender(
      <MemoryRouter initialEntries={['/forum/plant-care/34-different-thread']}>
        <AnnouncerProvider>
          <ThreadDetailPage />
        </AnnouncerProvider>
      </MemoryRouter>
    );
    await waitFor(() => expect(fetchThreadSpy).toHaveBeenCalledWith(34));
    expect(await screen.findByRole('button', { name: /^bookmark$/i })).toBeInTheDocument();

    // Thread A's request now fails — must not touch thread B's displayed state.
    rejectBookmark(new Error('Network error'));
    await waitFor(() => expect(loggerErrorSpy).toHaveBeenCalled());

    expect(screen.getByRole('button', { name: /^bookmark$/i })).toBeInTheDocument();
    expect(screen.queryByText('Network error')).not.toBeInTheDocument();
  });

  it('submits a published reply and shows it after refetch', async () => {
    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(createMockThread({ post_count: 0 }));
    const fetchPostsSpy = vi
      .spyOn(forumService, 'fetchPosts')
      .mockResolvedValueOnce({ items: [], meta: { count: 0, next: null, previous: null } })
      .mockResolvedValueOnce({
        items: [
          createMockPost({
            id: '99',
            body: [{ id: 'b', type: 'paragraph', value: '<p>my reply</p>' }],
          }),
        ],
        meta: { count: 0, next: null, previous: null },
      });
    vi.spyOn(forumService, 'createPost').mockResolvedValue({ id: '99', status: 'published' });

    renderThreadDetailPage();

    await screen.findByRole('button', { name: /Post Reply/i });
    await userEvent.type(screen.getByLabelText('Write a reply...'), 'my reply');
    await userEvent.click(screen.getByRole('button', { name: /Post Reply/i }));

    await waitFor(() => expect(screen.getByText('my reply')).toBeInTheDocument());
    expect(forumService.createPost).toHaveBeenCalledWith({
      thread: 12,
      content: '<p>my reply</p>',
    });
    expect(fetchPostsSpy).toHaveBeenCalledTimes(2);
    // The composer remounts (key bump) so it visibly clears after posting.
    expect(screen.getByLabelText('Write a reply...')).toHaveValue('');
  });

  // Defense-in-depth (todo 297): the reply already posted under whatever
  // identity the cookie carried by the time it landed — this cannot be
  // prevented, only detected and disclosed instead of the normal silent
  // "Reply posted." success announce (exactly how the live prod incident
  // went unnoticed).
  it('shows a distinct notice instead of the silent success announce when the acting identity changed mid-reply', async () => {
    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(createMockThread({ post_count: 0 }));
    vi.spyOn(forumService, 'fetchPosts')
      .mockResolvedValueOnce({ items: [], meta: { count: 0, next: null, previous: null } })
      .mockResolvedValueOnce({
        items: [createMockPost({ id: '99' })],
        meta: { count: 0, next: null, previous: null },
      });
    vi.spyOn(forumService, 'createPost').mockResolvedValue({ id: '99', status: 'published' });
    vi.mocked(useAuth).mockReturnValue({
      isAuthenticated: true,
      user: { id: 1, username: 'test-user' },
      revalidateIdentity: vi.fn().mockResolvedValue({ id: 2, username: 'someone-else' }),
    } as unknown as ReturnType<typeof useAuth>);

    renderThreadDetailPage();

    await screen.findByRole('button', { name: /Post Reply/i });
    await userEvent.type(screen.getByLabelText('Write a reply...'), 'my reply');
    await userEvent.click(screen.getByRole('button', { name: /Post Reply/i }));

    await waitFor(() => expect(screen.getByText(/posted as someone-else/i)).toBeInTheDocument());
    expect(document.querySelector('[data-announcer="polite"]')).not.toHaveTextContent(
      'Reply posted.'
    );
  });

  it('shows a combined identity-drift + moderation notice when the drifted reply was pending', async () => {
    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(createMockThread());
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue({
      items: [],
      meta: { count: 0 },
    });
    vi.spyOn(forumService, 'createPost').mockResolvedValue({ id: '99', status: 'pending' });
    vi.mocked(useAuth).mockReturnValue({
      isAuthenticated: true,
      user: { id: 1, username: 'test-user' },
      revalidateIdentity: vi.fn().mockResolvedValue({ id: 2, username: 'someone-else' }),
    } as unknown as ReturnType<typeof useAuth>);

    renderThreadDetailPage();

    await screen.findByRole('button', { name: /Post Reply/i });
    await userEvent.type(screen.getByLabelText('Write a reply...'), 'spammy');
    await userEvent.click(screen.getByRole('button', { name: /Post Reply/i }));

    await waitFor(() => expect(screen.getByText(/posted as someone-else/i)).toBeInTheDocument());
    expect(screen.getByText(/awaiting moderation/i)).toBeInTheDocument();
  });

  it('a published reply on a multi-page thread loads through to the new reply', async () => {
    // The new reply is the NEWEST post (oldest-first ordering) → last cursor page.
    // Reloading must follow the cursor to the end, not stop at page 1.
    const opening = createMockPost({
      id: '1',
      is_first_post: true,
      body: [{ id: 'b0', type: 'paragraph', value: '<p>opening</p>' }],
    });
    const reply = createMockPost({
      id: '99',
      body: [{ id: 'b9', type: 'paragraph', value: '<p>my reply</p>' }],
    });
    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(createMockThread({ post_count: 1 }));
    vi.spyOn(forumService, 'fetchPosts')
      .mockResolvedValueOnce({
        items: [opening],
        meta: { count: 0, next: 'cursor-2', previous: null },
      }) // mount: page 1
      .mockResolvedValueOnce({
        items: [opening],
        meta: { count: 0, next: 'cursor-2', previous: null },
      }) // reload: page 1
      .mockResolvedValueOnce({ items: [reply], meta: { count: 0, next: null, previous: null } }); // reload: page 2 (the reply)
    vi.spyOn(forumService, 'createPost').mockResolvedValue({ id: '99', status: 'published' });

    renderThreadDetailPage();

    await screen.findByRole('button', { name: /Post Reply/i });
    await userEvent.type(screen.getByLabelText('Write a reply...'), 'my reply');
    await userEvent.click(screen.getByRole('button', { name: /Post Reply/i }));

    await waitFor(() => expect(screen.getByText('my reply')).toBeInTheDocument());
    // Load More is gone — the cursor was followed to the end.
    expect(screen.queryByText(/Load More Posts/i)).not.toBeInTheDocument();
  });

  it('shows a moderation notice for a pending reply and does not refetch', async () => {
    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(createMockThread());
    const fetchPostsSpy = vi
      .spyOn(forumService, 'fetchPosts')
      .mockResolvedValue({ items: [], meta: { count: 0 } });
    vi.spyOn(forumService, 'createPost').mockResolvedValue({ id: '99', status: 'pending' });

    renderThreadDetailPage();

    await screen.findByRole('button', { name: /Post Reply/i });
    await userEvent.type(screen.getByLabelText('Write a reply...'), 'spammy');
    await userEvent.click(screen.getByRole('button', { name: /Post Reply/i }));

    await waitFor(() => expect(screen.getByText(/awaiting moderation/i)).toBeInTheDocument());
    expect(fetchPostsSpy).toHaveBeenCalledTimes(1); // initial load only — no refetch
  });

  it('deletes a post via the styled confirm dialog and removes it from the list (M24)', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm');
    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(createMockThread({ post_count: 1 }));
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue({
      items: [
        createMockPost({
          id: '5',
          can_delete: true,
          body: [{ id: 'b', type: 'paragraph', value: '<p>doomed</p>' }],
        }),
      ],
      meta: { count: 0, next: null, previous: null },
    });
    const deleteSpy = vi.spyOn(forumService, 'deletePost').mockResolvedValue(undefined);

    renderThreadDetailPage();

    await screen.findByText('doomed');
    // Clicking Delete opens a styled dialog — NOT a native window.confirm.
    await userEvent.click(screen.getByTitle('Delete post'));
    const dialog = await screen.findByRole('dialog');
    expect(confirmSpy).not.toHaveBeenCalled();
    // Confirm inside the dialog performs the delete.
    await userEvent.click(within(dialog).getByRole('button', { name: /^delete$/i }));

    await waitFor(() => expect(deleteSpy).toHaveBeenCalledWith('5'));
    expect(screen.queryByText('doomed')).not.toBeInTheDocument();
  });

  it('cancelling the delete dialog leaves the post intact (M24)', async () => {
    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(createMockThread({ post_count: 1 }));
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue({
      items: [createMockPost({ id: '5', can_delete: true })],
      meta: { count: 0, next: null, previous: null },
    });
    const deleteSpy = vi.spyOn(forumService, 'deletePost').mockResolvedValue(undefined);

    renderThreadDetailPage();

    await screen.findByTitle('Delete post');
    await userEvent.click(screen.getByTitle('Delete post'));
    const dialog = await screen.findByRole('dialog');
    await userEvent.click(within(dialog).getByRole('button', { name: /cancel/i }));

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(deleteSpy).not.toHaveBeenCalled();
  });

  it('prompts before discarding unsaved edits when switching edit targets (M27)', async () => {
    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(createMockThread());
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue({
      items: [
        createMockPost({
          id: '5',
          can_edit: true,
          body: [{ id: 'a', type: 'paragraph', value: '<p>first</p>' }],
        }),
        createMockPost({
          id: '6',
          can_edit: true,
          body: [{ id: 'b', type: 'paragraph', value: '<p>second</p>' }],
        }),
      ],
      meta: { count: 0, next: null, previous: null },
    });

    renderThreadDetailPage();

    // Edit the first post and make an unsaved change.
    const editButtons = await screen.findAllByTitle('Edit post');
    await userEvent.click(editButtons[0]);
    await userEvent.type(screen.getByLabelText('body'), ' changed');

    // The other post's Edit button now prompts instead of silently discarding.
    await userEvent.click(screen.getByTitle('Edit post'));
    expect(await screen.findByRole('dialog')).toHaveTextContent(/discard unsaved changes/i);
  });

  it('announces success after posting a published reply (M25)', async () => {
    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(createMockThread());
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue({
      items: [],
      meta: { count: 0, next: null, previous: null },
    });
    vi.spyOn(forumService, 'createPost').mockResolvedValue({ id: '99', status: 'published' });

    renderThreadDetailPage();

    await userEvent.type(await screen.findByLabelText('Write a reply...'), 'a reply');
    await userEvent.click(screen.getByRole('button', { name: /post reply/i }));

    await waitFor(() =>
      expect(document.querySelector('[data-announcer="polite"]')).toHaveTextContent('Reply posted.')
    );
  });

  it('toggling a reaction updates the displayed count', async () => {
    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(createMockThread());
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue({
      items: [createMockPost({ id: '5', reaction_counts: { like: 0 } })],
      meta: { count: 0, next: null, previous: null },
    });
    vi.spyOn(forumService, 'toggleReaction').mockResolvedValue({
      reaction_counts: { like: 1 },
      reacted: true,
    });

    renderThreadDetailPage();

    // Zero-count reactions are hidden at rest (de-cluttered row), so expand the
    // picker before the 'like' control is available.
    await userEvent.click(await screen.findByLabelText('Add reaction'));
    await userEvent.click(screen.getByLabelText('React like'));

    await waitFor(() => expect(screen.getByLabelText('React like')).toHaveTextContent('1'));
    expect(forumService.toggleReaction).toHaveBeenCalledWith('5', 'like');
    // M23: the toggle's `reacted: true` flips the button's pressed state (was
    // previously dropped, so the button never showed as reacted).
    expect(screen.getByLabelText('React like')).toHaveAttribute('aria-pressed', 'true');
  });

  it('un-reacting removes the type and flips aria-pressed back to false (M23)', async () => {
    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(createMockThread());
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue({
      // Starts reacted (pressed), count 2 (others reacted too).
      items: [createMockPost({ id: '5', reaction_counts: { like: 2 }, reacted: ['like'] })],
      meta: { count: 0, next: null, previous: null },
    });
    vi.spyOn(forumService, 'toggleReaction').mockResolvedValue({
      reaction_counts: { like: 1 },
      reacted: false, // the un-react branch of handleReact's ternary
    });

    renderThreadDetailPage();

    const likeBtn = await screen.findByRole('button', { name: 'React like' });
    expect(likeBtn).toHaveAttribute('aria-pressed', 'true');

    await userEvent.click(likeBtn);

    // Count drops to 1 (others still reacted) and the user's pressed state clears.
    await waitFor(() => expect(screen.getByLabelText('React like')).toHaveTextContent('1'));
    expect(screen.getByLabelText('React like')).toHaveAttribute('aria-pressed', 'false');
  });

  it('reports a post and shows a confirmation', async () => {
    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(createMockThread());
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue({
      items: [createMockPost({ id: '5', can_report: true })],
      meta: { count: 0, next: null, previous: null },
    });
    vi.spyOn(forumService, 'reportPost').mockResolvedValue(undefined);

    renderThreadDetailPage();

    await userEvent.click(await screen.findByTitle('Report post'));
    await userEvent.click(screen.getByText('Submit'));

    await waitFor(() => expect(screen.getByText('Reported')).toBeInTheDocument());
    expect(forumService.reportPost).toHaveBeenCalledWith('5', 'spam');
  });

  it('shows an error notice and does not falsely confirm when reporting fails', async () => {
    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(createMockThread());
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue({
      items: [createMockPost({ id: '5', can_report: true })],
      meta: { count: 0, next: null, previous: null },
    });
    vi.spyOn(forumService, 'reportPost').mockRejectedValue(
      new Error('You cannot report your own post.')
    );

    renderThreadDetailPage();

    await userEvent.click(await screen.findByTitle('Report post'));
    await userEvent.click(screen.getByText('Submit'));

    await screen.findByText('You cannot report your own post.');
    expect(screen.queryByText('Reported')).not.toBeInTheDocument();
  });

  it('blocks a post author and refetches the thread (todo 284/M9)', async () => {
    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(createMockThread());
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue({
      items: [createMockPost({ id: '5', can_block: true })],
      meta: { count: 0, next: null, previous: null },
    });
    vi.spyOn(forumService, 'blockUser').mockResolvedValue(undefined);

    renderThreadDetailPage();

    await userEvent.click(await screen.findByTitle('Block user'));

    expect(forumService.blockUser).toHaveBeenCalledWith('testuser');
    // setReloadKey triggers a full refetch — the initial mount call plus one more.
    await waitFor(() => expect(forumService.fetchPosts).toHaveBeenCalledTimes(2));
  });

  it('mutes a post author and refetches the thread (todo 347)', async () => {
    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(createMockThread());
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue({
      items: [createMockPost({ id: '5', can_mute: true })],
      meta: { count: 0, next: null, previous: null },
    });
    vi.spyOn(forumService, 'muteUser').mockResolvedValue(undefined);

    renderThreadDetailPage();

    await userEvent.click(await screen.findByTitle('Mute user'));

    expect(forumService.muteUser).toHaveBeenCalledWith('testuser');
    await waitFor(() => expect(forumService.fetchPosts).toHaveBeenCalledTimes(2));
  });

  it('shows an error notice when muting fails and does not refetch', async () => {
    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(createMockThread());
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue({
      items: [createMockPost({ id: '5', can_mute: true })],
      meta: { count: 0, next: null, previous: null },
    });
    vi.spyOn(forumService, 'muteUser').mockRejectedValue(new Error('Failed to mute user'));

    renderThreadDetailPage();

    await userEvent.click(await screen.findByTitle('Mute user'));

    await screen.findByText('Failed to mute user');
    expect(forumService.fetchPosts).toHaveBeenCalledTimes(1);
  });

  it('shows an error notice when blocking fails and does not refetch', async () => {
    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(createMockThread());
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue({
      items: [createMockPost({ id: '5', can_block: true })],
      meta: { count: 0, next: null, previous: null },
    });
    vi.spyOn(forumService, 'blockUser').mockRejectedValue(new Error('Failed to block user'));

    renderThreadDetailPage();

    await userEvent.click(await screen.findByTitle('Block user'));

    await screen.findByText('Failed to block user');
    expect(forumService.fetchPosts).toHaveBeenCalledTimes(1);
  });

  it('unblocks a post author and refetches the thread', async () => {
    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(createMockThread());
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue({
      items: [createMockPost({ id: '5', can_block: true, is_blocked: true })],
      meta: { count: 0, next: null, previous: null },
    });
    vi.spyOn(forumService, 'unblockUser').mockResolvedValue(undefined);

    renderThreadDetailPage();

    // Collapsed by default (is_blocked) — the inline placeholder Unblock works
    // without revealing first (a convenience, distinct from the header-row
    // Unblock which requires reveal).
    await userEvent.click(await screen.findByText('Unblock'));

    expect(forumService.unblockUser).toHaveBeenCalledWith('testuser');
    await waitFor(() => expect(forumService.fetchPosts).toHaveBeenCalledTimes(2));
  });

  it('edits a post and shows the new body', async () => {
    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(createMockThread());
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue({
      items: [
        createMockPost({
          id: '5',
          can_edit: true,
          body: [{ id: 'b', type: 'paragraph', value: '<p>old</p>' }],
        }),
      ],
      meta: { count: 0, next: null, previous: null },
    });
    vi.spyOn(forumService, 'updatePost').mockResolvedValue({
      post: createMockPost({
        id: '5',
        body: [{ id: 'b', type: 'paragraph', value: '<p>new body</p>' }],
      }),
      status: 'published',
    });

    renderThreadDetailPage();

    await screen.findByText('old');
    await userEvent.click(screen.getByTitle('Edit post'));
    // The editor opens on the existing body (forwarded by the stub above);
    // replace it, as a real edit would.
    const editBox = await screen.findByLabelText('body');
    expect(editBox).toHaveValue('<p>old</p>');
    await userEvent.clear(editBox);
    await userEvent.type(editBox, 'new body');
    await userEvent.click(screen.getByRole('button', { name: /^Save$/i }));

    await waitFor(() =>
      expect(forumService.updatePost).toHaveBeenCalledWith('5', { content: '<p>new body</p>' })
    );
    await waitFor(() => expect(screen.getByText('new body')).toBeInTheDocument());
  });

  it('shows Load More button when meta.next is present', async () => {
    const mockThread = createMockThread({ post_count: 45 });
    const mockPosts = {
      items: Array(20)
        .fill(null)
        .map((_, i) => createMockPost({ id: `post-${i}` })),
      meta: { count: 0, next: 'http://api/next-cursor', previous: null },
    };

    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(mockThread);
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue(mockPosts);

    renderThreadDetailPage();

    await waitFor(() => {
      expect(screen.getByText(/Load More Posts/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/25 remaining/i)).toBeInTheDocument();
  });

  it('hides Load More button when all posts are loaded', async () => {
    const mockThread = createMockThread();
    const mockPosts = {
      items: [createMockPost({ id: 'post-1' })],
      meta: { count: 1 }, // Only 1 post total
    };

    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(mockThread);
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue(mockPosts);

    renderThreadDetailPage();

    await waitFor(() => {
      expect(screen.queryByText(/Load More Posts/i)).not.toBeInTheDocument();
    });
  });

  it('loads more posts using cursor when Load More button is clicked', async () => {
    const nextCursorUrl = 'http://api/next-cursor';
    const mockThread = createMockThread({ post_count: 45 });
    const initialPosts = {
      items: Array(20)
        .fill(null)
        .map((_, i) => createMockPost({ id: `post-${i}` })),
      meta: { count: 0, next: nextCursorUrl, previous: null },
    };
    const morePosts = {
      items: Array(20)
        .fill(null)
        .map((_, i) => createMockPost({ id: `post-${i + 20}` })),
      meta: { count: 0, next: null, previous: null },
    };

    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(mockThread);
    const fetchPostsSpy = vi
      .spyOn(forumService, 'fetchPosts')
      .mockResolvedValueOnce(initialPosts)
      .mockResolvedValueOnce(morePosts);

    renderThreadDetailPage();

    await waitFor(() => {
      expect(screen.getByText(/Load More Posts/i)).toBeInTheDocument();
    });

    const loadMoreButton = screen.getByText(/Load More Posts/i);
    await userEvent.click(loadMoreButton);

    await waitFor(() => {
      expect(fetchPostsSpy).toHaveBeenCalledWith({
        thread: 12,
        cursor: nextCursorUrl,
      });
    });
  });

  it('deep-link to a post on a later cursor page pulls pages until it renders', async () => {
    // jsdom has no layout engine; the arrival effect calls scrollIntoView.
    Element.prototype.scrollIntoView = vi.fn();
    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(createMockThread({ post_count: 21 }));
    const fetchPostsSpy = vi
      .spyOn(forumService, 'fetchPosts')
      .mockResolvedValueOnce({
        items: [createMockPost({ id: '1' })],
        meta: { count: 0, next: 'cursor-page-2', previous: null },
      })
      .mockResolvedValueOnce({
        items: [createMockPost({ id: '21' })],
        meta: { count: 0, next: null, previous: null },
      });

    render(
      <MemoryRouter initialEntries={['/forum/3-plant-care/12-watering-tips#post-21']}>
        <AnnouncerProvider>
          <ThreadDetailPage />
        </AnnouncerProvider>
      </MemoryRouter>
    );

    // post-21 lives on page 2, absent from the first load — the arrival effect
    // must pull the next page for it to mount (it silently no-op'd before).
    await waitFor(() => expect(document.getElementById('post-21')).toBeInTheDocument());
    expect(fetchPostsSpy).toHaveBeenCalledWith({ thread: 12, cursor: 'cursor-page-2' });
  });

  it('deep-link chase does not retry forever when a later page keeps failing', async () => {
    Element.prototype.scrollIntoView = vi.fn();
    vi.spyOn(logger, 'error').mockImplementation(() => {});
    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(createMockThread({ post_count: 21 }));
    const fetchPostsSpy = vi
      .spyOn(forumService, 'fetchPosts')
      .mockResolvedValueOnce({
        items: [createMockPost({ id: '1' })],
        meta: { count: 0, next: 'cursor-page-2', previous: null },
      })
      .mockRejectedValue(new Error('page 2 keeps failing'));

    render(
      <MemoryRouter initialEntries={['/forum/3-plant-care/12-watering-tips#post-21']}>
        <AnnouncerProvider>
          <ThreadDetailPage />
        </AnnouncerProvider>
      </MemoryRouter>
    );

    // The failing page-2 fetch surfaces the error notice...
    await screen.findByText(/Failed to load more posts/i);
    // ...and is NOT retried in a loop: exactly one request for that cursor.
    const page2Calls = fetchPostsSpy.mock.calls.filter(
      (c) => (c[0] as { cursor?: string })?.cursor === 'cursor-page-2'
    );
    expect(page2Calls).toHaveLength(1);
  });

  it('scrolls to the anchored post once, not again when the post list changes', async () => {
    // jsdom defines scrollIntoView on HTMLElement.prototype; spy there so the
    // real call is captured (an Element.prototype assignment gets shadowed).
    const scrollSpy = vi.fn();
    HTMLElement.prototype.scrollIntoView = scrollSpy;
    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(createMockThread({ post_count: 25 }));
    vi.spyOn(forumService, 'fetchPosts')
      .mockResolvedValueOnce({
        items: [createMockPost({ id: '5' })],
        meta: { count: 0, next: 'cursor-page-2', previous: null },
      })
      .mockResolvedValueOnce({
        items: [createMockPost({ id: '6' })],
        meta: { count: 0, next: null, previous: null },
      });

    render(
      <MemoryRouter initialEntries={['/forum/3-plant-care/12-watering-tips#post-5']}>
        <AnnouncerProvider>
          <ThreadDetailPage />
        </AnnouncerProvider>
      </MemoryRouter>
    );

    // post-5 is on page 1 → found and scrolled once on arrival.
    await waitFor(() => expect(scrollSpy).toHaveBeenCalledTimes(1));

    // Loading more changes `posts`; the anchor must NOT be re-scrolled.
    await userEvent.click(screen.getByText(/Load More Posts/i));
    await waitFor(() => expect(document.getElementById('post-6')).toBeInTheDocument());
    expect(scrollSpy).toHaveBeenCalledTimes(1);
  });

  it('displays total post count in header from thread.post_count', async () => {
    const mockThread = createMockThread({ post_count: 150 });
    const mockPosts = {
      // Array.from re-invokes the factory per slot — Array(n).fill(x) reuses ONE
      // object (duplicate ids → React duplicate-key warnings; audit M21).
      items: Array.from({ length: 20 }, (_, i) => createMockPost({ id: `post-${i}` })),
      // meta.count is hardcoded 0 by the service; page uses thread.post_count instead
      meta: { count: 0, next: null, previous: null },
    };

    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(mockThread);
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue(mockPosts);

    renderThreadDetailPage();

    await waitFor(() => {
      expect(screen.getByText(/150 replies/i)).toBeInTheDocument();
    });
  });

  // --- Accepted answer (audit H6)

  /** A thread with an opening post + one reply, seeded from the given thread state. */
  function mockSolvableThread(threadOverrides = {}) {
    const thread = createMockThread({ can_mark_solution: true, ...threadOverrides });
    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(thread);
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue({
      items: [
        createMockPost({ id: '1', is_first_post: true }),
        createMockPost({ id: '2', is_first_post: false }),
      ],
      meta: { count: 0, next: null, previous: null },
    });
    return thread;
  }

  it('offers mark-as-answer on a reply but never on the opening post', async () => {
    mockSolvableThread();

    renderThreadDetailPage();

    await waitFor(() => expect(document.getElementById('post-2')).toBeInTheDocument());
    // One control, not two: the opening post is excluded even though the
    // viewer may mark — a question is not its own answer.
    expect(screen.getAllByRole('button', { name: /mark as answer/i })).toHaveLength(1);
    expect(
      within(document.getElementById('post-1')!).queryByRole('button', {
        name: /mark as answer/i,
      })
    ).not.toBeInTheDocument();
  });

  it('offers no mark-as-answer control when the backend says the viewer may not', async () => {
    mockSolvableThread({ can_mark_solution: false });

    renderThreadDetailPage();

    await waitFor(() => expect(document.getElementById('post-2')).toBeInTheDocument());
    expect(screen.queryByRole('button', { name: /mark as answer/i })).not.toBeInTheDocument();
  });

  it('marks the answer and highlights the post the SERVER confirmed', async () => {
    mockSolvableThread();
    const markSpy = vi
      .spyOn(forumService, 'markSolution')
      .mockResolvedValue({ is_solved: true, solved_post_id: 2, solved_at: '2026-07-31T10:00:00Z' });

    renderThreadDetailPage();

    await waitFor(() => expect(document.getElementById('post-2')).toBeInTheDocument());
    await userEvent.click(screen.getByRole('button', { name: /mark as answer/i }));

    await waitFor(() => expect(screen.getByText(/accepted answer/i)).toBeInTheDocument());
    expect(markSpy).toHaveBeenCalledWith(12, 2);
  });

  it('leaves the badge alone when the server refuses the mark', async () => {
    // Not optimistic on purpose: solved state is shared, and the backend can
    // legitimately refuse (422/403). A rejected request must not paint a badge
    // no other reader will see.
    mockSolvableThread();
    vi.spyOn(forumService, 'markSolution').mockRejectedValue(new Error('Nope'));
    vi.spyOn(logger, 'error').mockImplementation(() => {});

    renderThreadDetailPage();

    await waitFor(() => expect(document.getElementById('post-2')).toBeInTheDocument());
    await userEvent.click(screen.getByRole('button', { name: /mark as answer/i }));

    await waitFor(() => expect(screen.getByText('Nope')).toBeInTheDocument());
    expect(screen.queryByText(/accepted answer/i)).not.toBeInTheDocument();
  });

  it('clears the accepted answer when the already-accepted post is toggled', async () => {
    mockSolvableThread({ is_solved: true, solved_post_id: 2 });
    const clearSpy = vi
      .spyOn(forumService, 'clearSolution')
      .mockResolvedValue({ is_solved: false, solved_post_id: null, solved_at: null });

    renderThreadDetailPage();

    await waitFor(() => expect(screen.getByText(/accepted answer/i)).toBeInTheDocument());
    await userEvent.click(screen.getByRole('button', { name: /accepted/i }));

    await waitFor(() => expect(screen.queryByText(/accepted answer/i)).not.toBeInTheDocument());
    expect(clearSpy).toHaveBeenCalledWith(12);
  });

  /** The plant-ID snapshot card (audit M6). */
  describe('identification card', () => {
    const IDENTIFICATION = {
      image: { id: 7, url: 'http://x/plant.jpg', alt: 'plant.jpg', width: 800, height: 600 },
      provider: 'plant_id',
      candidates: [
        { name: 'Swiss cheese plant', scientific_name: 'Monstera deliciosa', confidence: 0.82 },
      ],
      created_at: '2026-07-31T10:00:00Z',
    };

    function mockThreadWith(threadOverrides = {}) {
      vi.spyOn(forumService, 'fetchThread').mockResolvedValue(createMockThread(threadOverrides));
      vi.spyOn(forumService, 'fetchPosts').mockResolvedValue({
        items: [
          createMockPost({ id: '1', is_first_post: true }),
          createMockPost({ id: '2', is_first_post: false }),
        ],
        meta: { count: 0, next: null, previous: null },
      });
    }

    it('renders the card above the opening post when the topic carries one', async () => {
      mockThreadWith({ identification: IDENTIFICATION });

      const { container } = renderThreadDetailPage();

      const card = await screen.findByRole('region', { name: /what the app suggested/i });
      const openingPost = document.getElementById('post-1')!;
      // Position, not just presence: the card must precede the question it
      // belongs to.
      expect(card.compareDocumentPosition(openingPost)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
      expect(container).toContainElement(openingPost);
    });

    it('renders no card when the topic has no snapshot', async () => {
      mockThreadWith({ identification: null });

      renderThreadDetailPage();

      await waitFor(() => expect(document.getElementById('post-1')).toBeInTheDocument());
      expect(
        screen.queryByRole('region', { name: /what the app suggested/i })
      ).not.toBeInTheDocument();
    });

    it('points the card at the accepted answer once the topic is solved', async () => {
      mockThreadWith({
        identification: IDENTIFICATION,
        is_solved: true,
        solved_post_id: 2,
      });

      renderThreadDetailPage();

      const link = await screen.findByRole('link', { name: /see the accepted answer/i });
      expect(link).toHaveAttribute('href', '#post-2');
    });
  });
});

describe('ThreadDetailPage new replies pill (todo 346)', () => {
  const setVisibility = (state: DocumentVisibilityState) => {
    Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => state });
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(ReactRouter.useParams).mockReturnValue({
      categorySlug: '3-plant-care',
      threadSlug: '12-watering-tips',
    });
    vi.mocked(useAuth).mockReturnValue(mockAuth(true));
    vi.mocked(forumService.fetchThreads).mockResolvedValue({
      items: [],
      meta: { next: null, count: 0 },
    });
    vi.mocked(blogService.fetchPopularPosts).mockResolvedValue([]);
    setVisibility('visible');
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
    setVisibility('visible');
  });

  const initialPosts = () => ({
    items: [createMockPost({ id: '1', is_first_post: true }), createMockPost({ id: '2' })],
    meta: { count: 0, next: null, previous: null },
  });

  it('polls post_count every 30 s with a peek read and offers to load what landed', async () => {
    const mockThread = createMockThread({ slug: 'watering-tips', post_count: 1 });
    const fetchThreadSpy = vi
      .spyOn(forumService, 'fetchThread')
      .mockResolvedValueOnce(mockThread)
      .mockResolvedValue({ ...mockThread, post_count: 3 });
    const fetchPostsSpy = vi.spyOn(forumService, 'fetchPosts').mockResolvedValue(initialPosts());

    renderThreadDetailPage();
    await screen.findByText(/1 replies/);
    expect(screen.queryByRole('button', { name: /new repl/i })).not.toBeInTheDocument();
    expect(fetchThreadSpy).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(NEW_REPLIES_POLL_INTERVAL_MS);
    });
    const pill = await screen.findByRole('button', { name: 'Load 2 new replies' });
    // Exactly one poll per interval (a faster timer than the constant would
    // fire more; a slower one, not at all), and the interval is the literal
    // the load argument in the spike doc is based on.
    expect(fetchThreadSpy).toHaveBeenCalledTimes(2);
    expect(NEW_REPLIES_POLL_INTERVAL_MS).toBe(30_000);
    // The poll is a peek: no view count, no read record, until the reader loads.
    expect(fetchThreadSpy).toHaveBeenLastCalledWith(12, { peek: true });
    // Nothing was inserted behind the reader's back.
    expect(screen.getByText(/1 replies/)).toBeInTheDocument();

    fetchPostsSpy.mockResolvedValue({
      items: [...initialPosts().items, createMockPost({ id: '3' }), createMockPost({ id: '4' })],
      meta: { count: 0, next: null, previous: null },
    });
    await act(async () => {
      pill.click();
    });
    await waitFor(() => {
      expect(screen.getByText(/3 replies/)).toBeInTheDocument();
    });
    expect(screen.queryByRole('button', { name: /new repl/i })).not.toBeInTheDocument();
    // Loading them IS reading them: a real (non-peek) read advances the record.
    expect(fetchThreadSpy).toHaveBeenLastCalledWith(12);
    expect(fetchPostsSpy).toHaveBeenLastCalledWith({ thread: 12 });
  });

  it('does no work while the tab is hidden and re-checks as soon as it is visible again', async () => {
    const mockThread = createMockThread({ slug: 'watering-tips', post_count: 1 });
    const fetchThreadSpy = vi.spyOn(forumService, 'fetchThread').mockResolvedValue(mockThread);
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue(initialPosts());

    renderThreadDetailPage();
    await screen.findByText(/1 replies/);
    expect(fetchThreadSpy).toHaveBeenCalledTimes(1);

    setVisibility('hidden');
    await act(async () => {
      await vi.advanceTimersByTimeAsync(NEW_REPLIES_POLL_INTERVAL_MS * 2);
    });
    expect(fetchThreadSpy).toHaveBeenCalledTimes(1);

    setVisibility('visible');
    await act(async () => {
      document.dispatchEvent(new Event('visibilitychange'));
    });
    await waitFor(() => {
      expect(fetchThreadSpy).toHaveBeenCalledTimes(2);
    });
    expect(fetchThreadSpy).toHaveBeenLastCalledWith(12, { peek: true });
  });

  it('never overlaps polls: a slow peek still in flight skips the next tick', async () => {
    const mockThread = createMockThread({ slug: 'watering-tips', post_count: 1 });
    let resolveSlow: (t: typeof mockThread) => void = () => {};
    const fetchThreadSpy = vi
      .spyOn(forumService, 'fetchThread')
      .mockResolvedValueOnce(mockThread)
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveSlow = resolve;
          })
      )
      .mockResolvedValue({ ...mockThread, post_count: 4 });
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue(initialPosts());

    renderThreadDetailPage();
    await screen.findByText(/1 replies/);

    // Two intervals pass while the first poll hangs: only ONE poll was issued.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(NEW_REPLIES_POLL_INTERVAL_MS * 2);
    });
    expect(fetchThreadSpy).toHaveBeenCalledTimes(2);

    // Once it settles, the next tick polls again and the pill reflects it.
    await act(async () => {
      resolveSlow({ ...mockThread, post_count: 2 });
    });
    await screen.findByRole('button', { name: 'Load 1 new reply' });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(NEW_REPLIES_POLL_INTERVAL_MS);
    });
    await screen.findByRole('button', { name: 'Load 3 new replies' });
    expect(fetchThreadSpy).toHaveBeenCalledTimes(3);
  });

  it("re-reads the baseline after the reader's own reply, so no ghost pill follows", async () => {
    // Two other replies landed before the reader posted: the refresh loads all
    // of them, and the baseline must be the fresh count (4), not old + 1 (2).
    // fireEvent (not userEvent) under fake timers: the mocked editor is a
    // plain textarea, and userEvent.setup() cannot re-stub the clipboard
    // once this file's module-level userEvent has installed it.
    const mockThread = createMockThread({ slug: 'watering-tips', post_count: 1 });
    vi.spyOn(forumService, 'fetchThread')
      .mockResolvedValueOnce(mockThread)
      .mockResolvedValue({ ...mockThread, post_count: 4 });
    vi.spyOn(forumService, 'fetchPosts')
      .mockResolvedValueOnce(initialPosts())
      .mockResolvedValue({
        items: [
          ...initialPosts().items,
          createMockPost({ id: '3' }),
          createMockPost({ id: '4' }),
          createMockPost({
            id: '99',
            body: [{ id: 'b', type: 'paragraph', value: '<p>my reply</p>' }],
          }),
        ],
        meta: { count: 0, next: null, previous: null },
      });
    vi.spyOn(forumService, 'createPost').mockResolvedValue({ id: '99', status: 'published' });

    renderThreadDetailPage();
    await screen.findByRole('button', { name: /Post Reply/i });
    fireEvent.change(screen.getByLabelText('Write a reply...'), { target: { value: 'my reply' } });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Post Reply/i }));
    });
    await waitFor(() => expect(screen.getByText('my reply')).toBeInTheDocument());
    expect(screen.getByText(/4 replies/)).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(NEW_REPLIES_POLL_INTERVAL_MS);
    });
    expect(screen.queryByRole('button', { name: /new repl/i })).not.toBeInTheDocument();
  });

  it('does not poll while the thread failed to load', async () => {
    const fetchThreadSpy = vi
      .spyOn(forumService, 'fetchThread')
      .mockRejectedValue(new Error('Thread not found'));
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue(initialPosts());

    renderThreadDetailPage();
    await screen.findByText(/Thread not found/);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(NEW_REPLIES_POLL_INTERVAL_MS * 2);
    });
    expect(fetchThreadSpy).toHaveBeenCalledTimes(1);
  });

  it('grows the Load More count instead of offering a pill while older pages remain', async () => {
    const mockThread = createMockThread({ slug: 'watering-tips', post_count: 25 });
    vi.spyOn(forumService, 'fetchThread')
      .mockResolvedValueOnce(mockThread)
      .mockResolvedValue({ ...mockThread, post_count: 27 });
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue({
      ...initialPosts(),
      meta: { count: 0, next: 'http://api/topics/12/posts/?cursor=p2', previous: null },
    });

    renderThreadDetailPage();
    await screen.findByRole('button', { name: /Load More Posts \(24 remaining\)/ });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(NEW_REPLIES_POLL_INTERVAL_MS);
    });
    await screen.findByRole('button', { name: /Load More Posts \(26 remaining\)/ });
    expect(screen.queryByRole('button', { name: /new repl/i })).not.toBeInTheDocument();
    expect(screen.getByText(/27 replies/)).toBeInTheDocument();
  });

  it('stops polling on unmount', async () => {
    const mockThread = createMockThread({ slug: 'watering-tips', post_count: 1 });
    const fetchThreadSpy = vi.spyOn(forumService, 'fetchThread').mockResolvedValue(mockThread);
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue(initialPosts());

    const { unmount } = renderThreadDetailPage();
    await screen.findByText(/1 replies/);
    unmount();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(NEW_REPLIES_POLL_INTERVAL_MS * 2);
    });
    expect(fetchThreadSpy).toHaveBeenCalledTimes(1);
  });

  it('keeps a failed poll silent and retries on the next tick', async () => {
    const mockThread = createMockThread({ slug: 'watering-tips', post_count: 1 });
    const fetchThreadSpy = vi
      .spyOn(forumService, 'fetchThread')
      .mockResolvedValueOnce(mockThread)
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValue({ ...mockThread, post_count: 2 });
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue(initialPosts());

    renderThreadDetailPage();
    await screen.findByText(/1 replies/);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(NEW_REPLIES_POLL_INTERVAL_MS);
    });
    expect(screen.queryByRole('button', { name: /new repl/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/Failed to load/)).not.toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(NEW_REPLIES_POLL_INTERVAL_MS);
    });
    await screen.findByRole('button', { name: 'Load 1 new reply' });
    expect(fetchThreadSpy).toHaveBeenCalledTimes(3);
  });
});

describe('ThreadDetailPage quote reply (todo 342)', () => {
  // Own top-level describe (real timers, cleared drafts): the poll suite above
  // runs on fake timers, and a stored draft from one case would otherwise be
  // restored into the next one's composer.
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    vi.mocked(ReactRouter.useParams).mockReturnValue({
      categorySlug: '3-plant-care',
      threadSlug: '12-watering-tips',
    });
    vi.mocked(useAuth).mockReturnValue(mockAuth(true));
    vi.mocked(forumService.fetchThreads).mockResolvedValue({
      items: [],
      meta: { next: null, count: 0 },
    });
    vi.mocked(blogService.fetchPopularPosts).mockResolvedValue([]);
  });

  const quotablePost = () =>
    createMockPost({
      id: '5',
      body: [{ id: 'b5', type: 'paragraph', value: '<p>Water it <strong>less</strong>.</p>' }],
    });

  it('puts a post_quote blockquote at the top of the reply draft, keeping what was typed below it', async () => {
    // jsdom defines scrollIntoView on HTMLElement.prototype; spy there so the
    // real call on the <form> is captured.
    const scrollSpy = vi.fn();
    HTMLElement.prototype.scrollIntoView = scrollSpy;
    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(createMockThread());
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue({
      items: [quotablePost()],
      meta: { count: 1, next: null, previous: null },
    });

    renderThreadDetailPage();
    await userEvent.type(await screen.findByLabelText('Write a reply...'), 'my draft');
    await userEvent.click(screen.getByTitle('Quote post'));

    // The composer is remounted on the new content (TipTap's `content` is
    // init-only); the quote leads and the existing draft follows it.
    expect(await screen.findByLabelText('Write a reply...')).toHaveValue(
      '<blockquote data-post-id="5"><p>Water it less.</p></blockquote><p>my draft</p>'
    );
    // Persisted like typed content — a remount fires no onChange.
    expect(sessionStorage.getItem('forum-draft:reply:12')).toContain('data-post-id="5"');
    expect(scrollSpy).toHaveBeenCalledTimes(1);
    expect(document.querySelector('[data-announcer="polite"]')).toHaveTextContent(
      "Quote of Test User's post added to your reply."
    );
  });

  it('announces each quote with its author, so two quotes in a row are read out twice', async () => {
    // The announcer swaps one live region's text; a repeat of the identical
    // string is not re-read, so the message must vary per quoted post.
    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(createMockThread());
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue({
      items: [
        createMockPost({
          id: '5',
          author: { username: 'ada', display_name: 'Ada', avatar: null, trust_level: 1 },
          body: [{ id: 'b5', type: 'paragraph', value: '<p>Water it less.</p>' }],
        }),
        createMockPost({
          id: '6',
          author: { username: 'bob', display_name: '', avatar: null, trust_level: 1 },
          body: [{ id: 'b6', type: 'paragraph', value: '<p>More light.</p>' }],
        }),
      ],
      meta: { count: 2, next: null, previous: null },
    });

    renderThreadDetailPage();
    const region = () => document.querySelector('[data-announcer="polite"]');
    await userEvent.click((await screen.findAllByTitle('Quote post'))[0]);
    const first = region()?.textContent;
    expect(first).toBe("Quote of Ada's post added to your reply.");

    await userEvent.click(screen.getAllByTitle('Quote post')[1]);
    // Falls back to the username when there is no display name.
    expect(region()?.textContent).toBe("Quote of bob's post added to your reply.");
    expect(region()?.textContent).not.toBe(first);
  });

  it('submits the quote as a post_quote block', async () => {
    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(createMockThread());
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue({
      items: [quotablePost()],
      meta: { count: 1, next: null, previous: null },
    });
    const createSpy = vi
      .spyOn(forumService, 'createPost')
      .mockResolvedValue({ id: '99', status: 'published' });

    renderThreadDetailPage();
    await userEvent.click(await screen.findByTitle('Quote post'));
    // A blank draft gets an empty paragraph after the quote so the caret
    // lands outside the blockquote; the quote alone enables Post Reply.
    expect(screen.getByLabelText('Write a reply...')).toHaveValue(
      '<blockquote data-post-id="5"><p>Water it less.</p></blockquote><p></p>'
    );
    await userEvent.click(screen.getByRole('button', { name: /post reply/i }));

    await waitFor(() => expect(createSpy).toHaveBeenCalledTimes(1));
    const { content } = createSpy.mock.calls[0][0];
    // What the (mocked) service sends is htmlToBodyBlocks(content) — the
    // block shape the server validates.
    expect(htmlToBodyBlocks(content)).toContainEqual({
      type: 'post_quote',
      value: { post: 5, text: 'Water it less.' },
    });
  });

  it('offers Quote only where there is a composer to quote into: not on a locked thread, not logged out', async () => {
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue({
      items: [quotablePost()],
      meta: { count: 1, next: null, previous: null },
    });
    const fetchThreadSpy = vi
      .spyOn(forumService, 'fetchThread')
      .mockResolvedValue(createMockThread({ is_locked: true }));

    const { unmount } = renderThreadDetailPage();
    await screen.findByText(/This thread is locked/);
    expect(screen.queryByTitle('Quote post')).not.toBeInTheDocument();
    unmount();

    fetchThreadSpy.mockResolvedValue(createMockThread());
    vi.mocked(useAuth).mockReturnValue(mockAuth(false));
    renderThreadDetailPage();
    await screen.findByText(/to post a reply/);
    expect(screen.queryByTitle('Quote post')).not.toBeInTheDocument();
  });

  it('refuses to quote a post with no text instead of inserting an empty quote', async () => {
    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(createMockThread());
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue({
      items: [
        createMockPost({
          id: '5',
          body: [{ id: 'i5', type: 'image', value: { id: 1, url: 'https://cdn/x.jpg' } }],
        }),
      ],
      meta: { count: 1, next: null, previous: null },
    });

    renderThreadDetailPage();
    await userEvent.click(await screen.findByTitle('Quote post'));

    // The server rejects an empty quote, so nothing is inserted and the
    // notice says why.
    expect(await screen.findByText('This post has no text to quote.')).toBeInTheDocument();
    expect(screen.getByLabelText('Write a reply...')).toHaveValue('');
    expect(sessionStorage.getItem('forum-draft:reply:12')).toBeNull();
  });
});
