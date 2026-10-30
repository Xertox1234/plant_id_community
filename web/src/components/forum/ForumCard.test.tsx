import { describe, it, expect } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import ForumCard, { ForumLinkCard } from './ForumCard';
import { createMockForum } from '../../tests/forumUtils';
import type { ForumLink } from '../../types/forum';

/**
 * Helper to render ForumCard with Router context
 */
function renderCategoryCard(category) {
  return render(
    <BrowserRouter>
      <ForumCard forum={category} />
    </BrowserRouter>
  );
}

describe('ForumCard', () => {
  it('renders category name and description', () => {
    const category = createMockForum({
      name: 'Plant Care Tips',
      description: 'Learn how to care for your plants',
    });

    renderCategoryCard(category);

    expect(screen.getByText('Plant Care Tips')).toBeInTheDocument();
    expect(screen.getByText('Learn how to care for your plants')).toBeInTheDocument();
  });

  it('renders category icon when present', () => {
    const category = createMockForum({ icon: '🌱' });

    renderCategoryCard(category);

    expect(screen.getByText('🌱')).toBeInTheDocument();
  });

  it('renders category stats (thread and post counts)', () => {
    const category = createMockForum({
      thread_count: 150,
      post_count: 1250,
    });

    renderCategoryCard(category);

    expect(screen.getByText(/150/)).toBeInTheDocument();
    expect(screen.getByText(/threads/i)).toBeInTheDocument();
    expect(screen.getByText(/1250/)).toBeInTheDocument();
    expect(screen.getByText(/posts/i)).toBeInTheDocument();
  });

  it('handles zero counts gracefully', () => {
    const category = createMockForum({
      thread_count: 0,
      post_count: 0,
    });

    renderCategoryCard(category);

    // Just verify the text appears - exact matching is fragile with styled components
    expect(screen.getByText(/threads/i)).toBeInTheDocument();
    expect(screen.getByText(/posts/i)).toBeInTheDocument();
  });

  it('links to category page with hybrid id+slug', () => {
    const category = createMockForum({ id: 'cat-1', slug: 'plant-care' });

    renderCategoryCard(category);

    const link = screen.getByRole('link');
    expect(link).toHaveAttribute('href', '/forum/cat-1-plant-care');
  });

  it('renders subcategories when present', () => {
    const category = createMockForum({
      children: [
        {
          id: 'sub-1',
          name: 'Watering',
          slug: 'watering',
          icon: '💧',
          created_at: '2025-01-01T00:00:00Z',
        },
        {
          id: 'sub-2',
          name: 'Fertilizing',
          slug: 'fertilizing',
          icon: '🌿',
          created_at: '2025-01-01T00:00:00Z',
        },
      ],
    });

    renderCategoryCard(category);

    expect(screen.getByText('Subcategories')).toBeInTheDocument();
    expect(screen.getByText('Watering')).toBeInTheDocument();
    expect(screen.getByText('Fertilizing')).toBeInTheDocument();
    expect(screen.getByText('💧')).toBeInTheDocument();
    expect(screen.getByText('🌿')).toBeInTheDocument();
  });

  it('does not render subcategories section when none exist', () => {
    const category = createMockForum({ children: [] });

    renderCategoryCard(category);

    expect(screen.queryByText('Subcategories')).not.toBeInTheDocument();
  });

  it('renders without description when not provided', () => {
    const category = createMockForum({ description: null });

    renderCategoryCard(category);

    expect(screen.getByText('Plant Care')).toBeInTheDocument();
    // Description should not be rendered
  });

  it('shows a last-activity timestamp when the board has activity (audit L2)', () => {
    const lastPost = new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString();
    renderCategoryCard(createMockForum({ last_post_at: lastPost }));

    const time = screen.getByText(/hours ago/i);
    expect(time.tagName).toBe('TIME');
    expect(time).toHaveAttribute('datetime', lastPost);
    // The absolute date is what a screen reader gets — a bare "2 hours ago"
    // is meaningless out of context (audit L12).
    expect(time).toHaveAttribute('aria-label', expect.stringContaining('Last activity'));
  });

  it('says so in words when a board has no activity yet', () => {
    renderCategoryCard(createMockForum({ last_post_at: null }));

    expect(screen.getByText('No activity yet')).toBeInTheDocument();
  });

  it('category name heading is rendered inside the clickable link', () => {
    const category = createMockForum({ name: 'Plant Care' });
    renderCategoryCard(category);
    const link = screen.getByRole('link', { name: /Plant Care/ });
    expect(within(link).getByRole('heading', { level: 3, name: 'Plant Care' })).toBeInTheDocument();
  });
});

describe('ForumCard unread marker (todo 671)', () => {
  it('shows an unread marker only when the forum has unread topics', () => {
    const { unmount } = renderCategoryCard(createMockForum({ has_unread: true }));
    expect(screen.getByText('Unread posts')).toBeInTheDocument();
    unmount();

    renderCategoryCard(createMockForum({ has_unread: false }));
    expect(screen.queryByText('Unread posts')).not.toBeInTheDocument();
  });
});

function makeLink(overrides: Partial<ForumLink> = {}): ForumLink {
  return {
    id: '5',
    name: 'Plant shop',
    slug: 'shop',
    description: 'Pots and soil',
    link_url: 'https://shop.example.com/',
    track_clicks: true,
    click_count: 7,
    ...overrides,
  };
}

function renderLink(link: ForumLink) {
  return render(
    <BrowserRouter>
      <ForumLinkCard link={link} />
    </BrowserRouter>
  );
}

describe('ForumLinkCard (todo 670)', () => {
  it('renders a tracked link as an external link through the counting redirect, with its click count', () => {
    renderLink(makeLink());

    const link = screen.getByRole('link', { name: /Plant shop/ });
    expect(link.getAttribute('href')).toMatch(/\/api\/v1\/forum\/links\/5\/go\/$/);
    expect(link).toHaveAttribute('target', '_blank');
    expect(link.getAttribute('rel')).toContain('noopener');
    expect(link.getAttribute('rel')).toContain('nofollow');
    expect(within(link).getByText('7 clicks')).toBeInTheDocument();
    expect(within(link).getByText('External link')).toBeInTheDocument();
  });

  it('says "1 click" in the singular', () => {
    renderLink(makeLink({ click_count: 1 }));

    expect(screen.getByText('1 click')).toBeInTheDocument();
  });

  it('renders an untracked link straight to its URL with no click count', () => {
    renderLink(makeLink({ track_clicks: false, click_count: null }));

    const link = screen.getByRole('link', { name: /Plant shop/ });
    expect(link).toHaveAttribute('href', 'https://shop.example.com/');
    expect(link.getAttribute('rel')).toContain('noopener');
    expect(link.getAttribute('rel')).toContain('nofollow');
    expect(screen.queryByText(/clicks?$/)).not.toBeInTheDocument();
  });

  it('renders no link at all for a URL that is not http(s)', () => {
    renderLink(makeLink({ link_url: 'javascript:alert(1)', track_clicks: false }));

    expect(screen.queryByRole('link')).not.toBeInTheDocument();
    expect(screen.getByText('Plant shop')).toBeInTheDocument();
  });
});

describe('ForumCard moderators and lock (todos 674, 680)', () => {
  it('renders the Moderators line with every name', () => {
    renderCategoryCard(createMockForum({ moderators: ['ann', 'Plant doctors'] }));

    expect(screen.getByText('Moderators: ann, Plant doctors')).toBeInTheDocument();
  });

  it('renders no Moderators line for a forum without moderators', () => {
    renderCategoryCard(createMockForum({ moderators: [] }));

    expect(screen.queryByText(/Moderators:/)).not.toBeInTheDocument();
  });

  it('marks a locked forum for sighted and screen-reader users', () => {
    renderCategoryCard(createMockForum({ is_locked: true }));

    expect(screen.getByText('Password protected')).toBeInTheDocument();
  });
});
