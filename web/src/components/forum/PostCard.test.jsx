import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import PostCard from './PostCard';
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
        username: 'plantlover',
        display_name: null,
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

  it('does not render reactions section when no reactions', () => {
    const post = createMockPost({
      reaction_counts: {},
    });

    renderPostCard(post);

    // Should not have reaction buttons
    expect(screen.queryByText('👍')).not.toBeInTheDocument();
  });

  it('does not render reactions with zero count', () => {
    const post = createMockPost({
      reaction_counts: {
        like: 0,
        love: 2,
      },
    });

    renderPostCard(post);

    // Should only show love reaction (count > 0)
    expect(screen.queryByText('👍')).not.toBeInTheDocument();
    expect(screen.getByText('❤️')).toBeInTheDocument();
  });

  it('applies green border for first post', () => {
    const post = createMockPost({ is_first_post: true });

    const { container } = renderPostCard(post);

    const card = container.querySelector('.border-green-500');
    expect(card).toBeInTheDocument();
  });

  it('renders author avatar with first letter', () => {
    const post = createMockPost({
      author: {
        id: 1,
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
        username: 'plantlover',
        display_name: null,
        trust_level: 'basic',
      },
    });

    renderPostCard(post);

    // Should show first letter of username
    expect(screen.getByText('p')).toBeInTheDocument();
  });
});
