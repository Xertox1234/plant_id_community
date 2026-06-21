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

// Mock the forumService and AuthContext (PostCard calls useAuth internally)
vi.mock('../../services/forumService');
vi.mock('../../contexts/AuthContext', () => ({
  useAuth: vi.fn(() => ({ user: null, isAuthenticated: false })),
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

  it('shows read-only notice instead of reply form', async () => {
    const mockThread = createMockThread();

    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(mockThread);
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue({
      items: [],
      meta: { count: 0 },
    });

    renderThreadDetailPage();

    await waitFor(() => {
      expect(screen.getByText(/read-only/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/coming soon/i)).toBeInTheDocument();
  });

  it('does not show reply form or Post Your Reply heading', async () => {
    const mockThread = createMockThread();

    vi.spyOn(forumService, 'fetchThread').mockResolvedValue(mockThread);
    vi.spyOn(forumService, 'fetchPosts').mockResolvedValue({
      items: [],
      meta: { count: 0 },
    });

    renderThreadDetailPage();

    // Block until the loaded state is rendered (the read-only notice appears),
    // then assert the write UI is absent.
    await screen.findByText(/read-only/i);

    expect(screen.queryByText(/Post Your Reply/i)).not.toBeInTheDocument();
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Post Reply/i })).not.toBeInTheDocument();
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
