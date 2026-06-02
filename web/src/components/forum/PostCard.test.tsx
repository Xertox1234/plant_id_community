import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import PostCard from './PostCard';
import { useAuth } from '../../contexts/AuthContext';
import { createMockPost } from '../../tests/forumUtils';

// Mock the AuthContext
vi.mock('../../contexts/AuthContext', () => ({
  useAuth: vi.fn(() => ({
    user: null,
    isAuthenticated: false,
  })),
}));

/**
 * Helper to render PostCard with Router context
 */
function renderPostCard(post, onEdit = vi.fn(), onDelete = vi.fn()) {
  return render(
    <BrowserRouter>
      <PostCard post={post} onEdit={onEdit} onDelete={onDelete} />
    </BrowserRouter>
  );
}

describe('PostCard', () => {
  it('renders post author information', () => {
    const post = createMockPost({
      author: {
        id: 1,
        email: 'plantlover@example.com',
        username: 'plantlover',
        display_name: 'Green Thumb',
        trust_level: 'member',
      },
    });

    renderPostCard(post);

    expect(screen.getByText('Green Thumb')).toBeInTheDocument();
    expect(screen.getByText('member')).toBeInTheDocument();
  });

  it('falls back to username when display_name is missing', () => {
    const post = createMockPost({
      author: {
        id: 1,
        email: 'plantlover@example.com',
        username: 'plantlover',
        display_name: undefined,
        trust_level: 'basic',
      },
    });

    renderPostCard(post);

    expect(screen.getByText('plantlover')).toBeInTheDocument();
  });

  it('renders "Original Post" badge for first post', () => {
    const post = createMockPost({ is_first_post: true });

    renderPostCard(post);

    expect(screen.getByText('Original Post')).toBeInTheDocument();
  });

  it('does not show "Original Post" badge for replies', () => {
    const post = createMockPost({ is_first_post: false });

    renderPostCard(post);

    expect(screen.queryByText('Original Post')).not.toBeInTheDocument();
  });

  it('sanitizes HTML content to prevent XSS', () => {
    const post = createMockPost({
      content_raw: '<p>Safe content</p><script>alert("xss")</script>',
    });

    const { container } = renderPostCard(post);

    // Should render safe content
    expect(screen.getByText('Safe content')).toBeInTheDocument();

    // Should NOT render script tag
    const scripts = container.querySelectorAll('script');
    expect(scripts.length).toBe(0);
  });

  it('allows safe HTML tags (paragraphs, bold, links)', () => {
    const post = createMockPost({
      content_raw: '<p>Test <strong>bold</strong> and <a href="#">link</a></p>',
    });

    const { container } = renderPostCard(post);

    expect(container.querySelector('p')).toBeInTheDocument();
    expect(container.querySelector('strong')).toBeInTheDocument();
    expect(container.querySelector('a')).toBeInTheDocument();
  });

  it('displays formatted relative timestamp', () => {
    const post = createMockPost({
      created_at: new Date(Date.now() - 1000 * 60 * 45).toISOString(), // 45 min ago
    });

    renderPostCard(post);

    expect(screen.getByText(/ago/i)).toBeInTheDocument();
  });

  it('shows edit timestamp when post was edited', () => {
    const post = createMockPost({
      edited_at: new Date(Date.now() - 1000 * 60 * 15).toISOString(), // 15 min ago
      edited_by: {
        username: 'moderator',
        display_name: 'Mod Team',
      },
    });

    renderPostCard(post);

    expect(screen.getByText(/edited/i)).toBeInTheDocument();
    expect(screen.getByText(/Mod Team/i)).toBeInTheDocument();
  });

  it('does not show edit info when post has not been edited', () => {
    const post = createMockPost({
      edited_at: null,
      edited_by: null,
    });

    renderPostCard(post);

    expect(screen.queryByText(/edited/i)).not.toBeInTheDocument();
  });

  it('renders reaction counts with emojis', () => {
    const post = createMockPost({
      reaction_counts: {
        like: 5,
        love: 2,
        helpful: 3,
        thanks: 1,
      },
    });

    renderPostCard(post);

    expect(screen.getByText('👍')).toBeInTheDocument();
    expect(screen.getByText('5')).toBeInTheDocument();
    expect(screen.getByText('❤️')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText('💡')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByText('🙏')).toBeInTheDocument();
    expect(screen.getByText('1')).toBeInTheDocument();
  });

  it('always renders the four reaction buttons, defaulting counts to 0', () => {
    const post = createMockPost({
      reaction_counts: {},
    });

    renderPostCard(post);

    // All four reaction buttons render so a user can add a first reaction.
    expect(screen.getByLabelText('React like')).toBeInTheDocument();
    expect(screen.getByLabelText('React love')).toBeInTheDocument();
    expect(screen.getByLabelText('React helpful')).toBeInTheDocument();
    expect(screen.getByLabelText('React thanks')).toBeInTheDocument();
    expect(screen.getAllByText('0')).toHaveLength(4);
  });

  it('shows each reaction type with its count (0 when absent)', () => {
    const post = createMockPost({
      reaction_counts: {
        like: 0,
        love: 2,
      },
    });

    renderPostCard(post);

    expect(screen.getByLabelText('React love')).toHaveTextContent('2');
    expect(screen.getByLabelText('React like')).toHaveTextContent('0');
  });

  it('calls onReact with the post id and reaction type when clicked', async () => {
    const onReact = vi.fn();
    const post = createMockPost({ id: 'post-9' });

    render(
      <BrowserRouter>
        <PostCard post={post} onReact={onReact} />
      </BrowserRouter>
    );

    await userEvent.click(screen.getByLabelText('React like'));

    expect(onReact).toHaveBeenCalledWith('post-9', 'like');
  });

  it('applies green border for first post', () => {
    const post = createMockPost({ is_first_post: true });

    const { container } = renderPostCard(post);

    const card = container.querySelector('.border-primary');
    expect(card).toBeInTheDocument();
  });

  it('renders author avatar with first letter', () => {
    const post = createMockPost({
      author: {
        id: 1,
        email: 'gardener@example.com',
        username: 'gardener',
        display_name: 'Garden Expert',
        trust_level: 'regular',
      },
    });

    renderPostCard(post);

    // Should show first letter of display_name
    expect(screen.getByText('G')).toBeInTheDocument();
  });

  it('uses username first letter when display_name is missing', () => {
    const post = createMockPost({
      author: {
        id: 1,
        email: 'plantlover@example.com',
        username: 'plantlover',
        display_name: undefined,
        trust_level: 'basic',
      },
    });

    renderPostCard(post);

    // Should show first letter of username
    expect(screen.getByText('p')).toBeInTheDocument();
  });

  it('edit and delete buttons are in the DOM for the post owner without hover', () => {
    vi.mocked(useAuth).mockReturnValueOnce({
      user: { id: 1, email: 'owner@example.com', is_staff: false, is_moderator: false },
      isAuthenticated: true,
      isLoading: false,
      error: null,
      login: vi.fn(),
      logout: vi.fn(),
      signup: vi.fn(),
      clearError: vi.fn(),
    });

    const post = createMockPost({
      author: { id: 1, username: 'owner', email: '', display_name: 'Owner', trust_level: 'member' },
    });

    renderPostCard(post);

    // Buttons must be in the DOM regardless of hover state (CSS hides them on md+).
    expect(screen.getByTitle('Edit post')).toBeInTheDocument();
    expect(screen.getByTitle('Delete post')).toBeInTheDocument();
  });
});
