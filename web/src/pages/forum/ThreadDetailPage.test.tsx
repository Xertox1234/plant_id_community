import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import * as ReactRouter from 'react-router-dom';
import ThreadDetailPage from './ThreadDetailPage';
import { createMockThread, createMockPost } from '../../tests/forumUtils';
import * as forumService from '../../services/forumService';

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

describe('ThreadDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Mock useParams to return hybrid id-slug params; lookups use the leading id.
    vi.mocked(ReactRouter.useParams).mockReturnValue({
      categorySlug: '3-plant-care',
      threadSlug: '12-watering-tips',
    });
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

    await screen.findByLabelText('React like');
    expect(screen.getByLabelText('React like')).toHaveTextContent('0');
    await userEvent.click(screen.getByLabelText('React like'));

    await waitFor(() => expect(screen.getByLabelText('React like')).toHaveTextContent('1'));
    expect(forumService.toggleReaction).toHaveBeenCalledWith('5', 'like');
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

  it('displays total post count in header from thread.post_count', async () => {
    const mockThread = createMockThread({ post_count: 150 });
    const mockPosts = {
      items: Array(20).fill(createMockPost()),
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
