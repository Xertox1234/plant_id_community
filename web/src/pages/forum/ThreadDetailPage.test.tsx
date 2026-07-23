import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import * as ReactRouter from 'react-router-dom';
import ThreadDetailPage from './ThreadDetailPage';
import { createMockThread, createMockPost } from '../../tests/forumUtils';
import * as forumService from '../../services/forumService';
import { useAuth } from '../../contexts/AuthContext';
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
vi.mock('../../services/forumService');
vi.mock('../../contexts/AuthContext', () => ({ useAuth: vi.fn() }));
vi.mock('../../components/forum/TipTapEditor', () => ({
  default: ({
    onChange,
    placeholder,
  }: {
    onChange?: (html: string) => void;
    placeholder?: string;
  }) => (
    <textarea
      aria-label={placeholder || 'body'}
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
      <ThreadDetailPage />
    </MemoryRouter>
  );
}

const mockAuth = (isAuthenticated: boolean) =>
  ({ user: isAuthenticated ? { id: 1 } : null, isAuthenticated }) as unknown as ReturnType<
    typeof useAuth
  >;

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
        id: 1,
        email: 'gardener@example.com',
        username: 'gardener',
        display_name: 'Master Gardener',
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
    expect(breadcrumb).toHaveTextContent('Forums');
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
      expect(screen.getByText(/📌 Pinned/i)).toBeInTheDocument();
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
      expect(screen.getByText(/🔒 Locked/i)).toBeInTheDocument();
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

    expect(await screen.findByRole('button', { name: /🔔 Follow/i })).toBeInTheDocument();
  });

  it('shows a Following button for an authenticated user on a subscribed thread', async () => {
    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(
      createMockThread({ is_subscribed: true })
    );
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue({ items: [], meta: { count: 0 } });

    renderThreadDetailPage();

    expect(await screen.findByRole('button', { name: /🔕 Following/i })).toBeInTheDocument();
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

    await userEvent.click(await screen.findByRole('button', { name: /🔔 Follow/i }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /🔕 Following/i })).toBeInTheDocument();
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

    await userEvent.click(await screen.findByRole('button', { name: /🔕 Following/i }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /🔔 Follow/i })).toBeInTheDocument();
    });
    expect(unsubscribeSpy).toHaveBeenCalledWith(12);
  });

  it('rolls back the optimistic Follow toggle and shows a notice when the request fails', async () => {
    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(
      createMockThread({ is_subscribed: false })
    );
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue({ items: [], meta: { count: 0 } });
    vi.spyOn(forumService, 'subscribeToTopic').mockRejectedValue(new Error('Network error'));

    renderThreadDetailPage();

    await userEvent.click(await screen.findByRole('button', { name: /🔔 Follow/i }));

    await screen.findByText('Network error');
    expect(screen.getByRole('button', { name: /🔔 Follow/i })).toBeInTheDocument();
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

    await userEvent.click(await screen.findByRole('button', { name: /🔔 Follow/i }));
    expect(screen.getByRole('button', { name: /🔕 Following/i })).toBeDisabled();

    vi.mocked(ReactRouter.useParams).mockReturnValue({
      categorySlug: '3-plant-care',
      threadSlug: '34-different-thread',
    });
    rerender(
      <MemoryRouter initialEntries={['/forum/plant-care/34-different-thread']}>
        <ThreadDetailPage />
      </MemoryRouter>
    );

    await waitFor(() => expect(fetchThreadSpy).toHaveBeenCalledWith(34));
    expect(await screen.findByRole('button', { name: /🔔 Follow/i })).not.toBeDisabled();
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

    await userEvent.click(await screen.findByRole('button', { name: /🔔 Follow/i }));
    expect(screen.getByRole('button', { name: /🔕 Following/i })).toBeInTheDocument();

    vi.mocked(ReactRouter.useParams).mockReturnValue({
      categorySlug: '3-plant-care',
      threadSlug: '34-different-thread',
    });
    rerender(
      <MemoryRouter initialEntries={['/forum/plant-care/34-different-thread']}>
        <ThreadDetailPage />
      </MemoryRouter>
    );
    await waitFor(() => expect(fetchThreadSpy).toHaveBeenCalledWith(34));
    expect(await screen.findByRole('button', { name: /🔔 Follow/i })).toBeInTheDocument();

    // Thread A's request now fails — must not touch thread B's displayed state.
    rejectSubscribe(new Error('Network error'));
    await waitFor(() => expect(loggerErrorSpy).toHaveBeenCalled());

    expect(screen.getByRole('button', { name: /🔔 Follow/i })).toBeInTheDocument();
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

  it('deletes a post after confirmation and removes it from the list', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
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
    await userEvent.click(screen.getByTitle('Delete post'));

    await waitFor(() => expect(deleteSpy).toHaveBeenCalledWith('5'));
    expect(screen.queryByText('doomed')).not.toBeInTheDocument();
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
    await userEvent.type(await screen.findByLabelText('body'), 'new body');
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
        <ThreadDetailPage />
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
        <ThreadDetailPage />
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
        <ThreadDetailPage />
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
});
