import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import ThreadCard from './ThreadCard';
import { createMockThread } from '../../tests/forumUtils';

/**
 * Helper to render ThreadCard with Router context
 */
function renderThreadCard(thread, compact = false) {
  return render(
    <BrowserRouter>
      <ThreadCard thread={thread} compact={compact} />
    </BrowserRouter>
  );
}

describe('ThreadCard', () => {
  it('renders thread title and excerpt', () => {
    const thread = createMockThread({
      title: 'How to water succulents?',
      excerpt: 'Looking for watering tips',
    });

    renderThreadCard(thread);

    expect(screen.getByText('How to water succulents?')).toBeInTheDocument();
    expect(screen.getByText('Looking for watering tips')).toBeInTheDocument();
  });

  it('renders author display name', () => {
    const thread = createMockThread({
      author: {
        id: 1,
        username: 'plantlover',
        display_name: 'Plant Enthusiast',
      },
    });

    renderThreadCard(thread);

    expect(screen.getByText('Plant Enthusiast')).toBeInTheDocument();
  });

  it('falls back to username when display_name is missing', () => {
    const thread = createMockThread({
      author: {
        id: 1,
        username: 'plantlover',
        display_name: null,
      },
    });

    renderThreadCard(thread);

    expect(screen.getByText('plantlover')).toBeInTheDocument();
  });

  it('renders pinned badge when thread is pinned', () => {
    const thread = createMockThread({ is_pinned: true });

    renderThreadCard(thread);

    expect(screen.getByText(/📌.*pinned/i)).toBeInTheDocument();
  });

  it('renders locked badge when thread is locked', () => {
    const thread = createMockThread({ is_locked: true });

    renderThreadCard(thread);

    expect(screen.getByText(/🔒.*locked/i)).toBeInTheDocument();
  });

  it('renders both pinned and locked badges when applicable', () => {
    const thread = createMockThread({
      is_pinned: true,
      is_locked: true,
    });

    renderThreadCard(thread);

    expect(screen.getByText(/pinned/i)).toBeInTheDocument();
    expect(screen.getByText(/locked/i)).toBeInTheDocument();
  });

  it('displays thread stats (post count and view count)', () => {
    const thread = createMockThread({
      post_count: 25,
      view_count: 350,
    });

    const { container } = renderThreadCard(thread);

    // Check for stats in title attributes
    expect(container.querySelector('[title*="25 replies"]')).toBeInTheDocument();
    expect(container.querySelector('[title*="350 views"]')).toBeInTheDocument();
  });

  it('handles zero stats gracefully', () => {
    const thread = createMockThread({
      post_count: 0,
      view_count: 0,
    });

    const { container } = renderThreadCard(thread);

    // Check for zero stats in title attributes
    expect(container.querySelector('[title*="0 replies"]')).toBeInTheDocument();
    expect(container.querySelector('[title*="0 views"]')).toBeInTheDocument();
  });

  it('formats last activity date as relative time', () => {
    const thread = createMockThread({
      last_activity_at: new Date(Date.now() - 1000 * 60 * 30).toISOString(), // 30 minutes ago
    });

    renderThreadCard(thread);

    // Should show relative time like "30 minutes ago"
    expect(screen.getByText(/ago/i)).toBeInTheDocument();
  });

  it('links to correct thread URL', () => {
    const thread = createMockThread({
      slug: 'watering-tips',
      category: {
        id: 'cat-123',
        name: 'Plant Care',
        slug: 'plant-care',
        icon: '🌱',
      },
    });

    renderThreadCard(thread);

    const link = screen.getByRole('link');
    expect(link).toHaveAttribute('href', '/forum/plant-care/watering-tips');
  });

  it('hides excerpt in compact mode', () => {
    const thread = createMockThread({
      excerpt: 'This should not appear in compact mode',
    });

    renderThreadCard(thread, true);

    expect(screen.queryByText('This should not appear in compact mode')).not.toBeInTheDocument();
  });

  it('shows category name in compact mode', () => {
    const thread = createMockThread({
      category: {
        id: 'cat-123',
        name: 'Plant Care',
        slug: 'plant-care',
        icon: '🌱',
      },
    });

    renderThreadCard(thread, true);

    expect(screen.getByText('Plant Care')).toBeInTheDocument();
    expect(screen.getByText('🌱')).toBeInTheDocument();
  });

  it('applies pinned background styling', () => {
    const thread = createMockThread({ is_pinned: true });

    const { container } = renderThreadCard(thread);

    const card = container.querySelector('.bg-yellow-50');
    expect(card).toBeInTheDocument();
  });

  it('applies opacity for locked threads', () => {
    const thread = createMockThread({ is_locked: true });

    const { container } = renderThreadCard(thread);

    const card = container.querySelector('.opacity-75');
    expect(card).toBeInTheDocument();
  });

  it('renders with correct compact padding', () => {
    const thread = createMockThread();

    const { container } = renderThreadCard(thread, true);

    const card = container.querySelector('.p-3');
    expect(card).toBeInTheDocument();
  });
});
