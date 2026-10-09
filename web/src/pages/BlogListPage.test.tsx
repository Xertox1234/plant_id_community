import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import BlogListPage from './BlogListPage';
import { RAIL_CONTAINER_ID, RAIL_MEDIA_QUERY } from '../components/layout/RailSlot';
import { fetchBlogPosts, fetchPopularPosts, fetchCategories } from '../services/blogService';
import { createMockBlogPost } from '@/tests/utils';
import type { BlogPost } from '@/types';

vi.mock('../services/blogService', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/blogService')>();
  return {
    ...actual,
    fetchBlogPosts: vi.fn(),
    fetchPopularPosts: vi.fn(),
    fetchCategories: vi.fn(),
  };
});

const mockFetchPosts = vi.mocked(fetchBlogPosts);
const mockFetchPopular = vi.mocked(fetchPopularPosts);
const mockFetchCategories = vi.mocked(fetchCategories);

function post(slug: string, title: string): BlogPost {
  return createMockBlogPost({
    id: Math.random(),
    meta: { type: 'blog.BlogPostPage', detail_url: '', html_url: '', slug, first_published_at: '' },
    slug,
    title,
    author: { display_name: 'June Park' },
    categories: [{ id: 1, name: 'Care', slug: 'care' }],
    excerpt: undefined,
    featured_image: undefined,
    featured_image_thumb: undefined,
  });
}

function renderPage(initialEntries: string[] = ['/blog']) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <BlogListPage />
    </MemoryRouter>
  );
}

beforeEach(() => {
  // Block bodies, not implicit returns — Vitest 4 registers an implicit
  // return as teardown (docs/rules/testing.md).
  mockFetchPosts.mockResolvedValue({
    items: [post('killed-by-kindness', 'Killed by kindness')],
    meta: { total_count: 1 },
  });
  mockFetchPopular.mockResolvedValue([
    post('fiddle-leaf-adjusting', 'Your fiddle leaf isn’t dying, it’s adjusting'),
  ]);
  mockFetchCategories.mockResolvedValue([
    { id: 1, name: 'Care', slug: 'care' },
    { id: 2, name: 'Design', slug: 'design' },
  ]);
});

describe('BlogListPage', () => {
  it('renders the locked Canopy hero copy', async () => {
    renderPage();
    expect(await screen.findByText('Do less to your plants.')).toBeInTheDocument();
    expect(screen.getByText('The blog · new posts weekly')).toBeInTheDocument();
    expect(screen.getByText(/killed by kindness\./)).toBeInTheDocument();
    // "Read the latest" is a Button until the limit-1 latest fetch resolves,
    // then a link — assert by text here; the link form is the next test.
    expect(screen.getByText('Read the latest')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'All topics →' })).toBeInTheDocument();
  });

  it('puts the newsletter signup in the page when the rail is hidden (todo 409)', async () => {
    // jsdom matches no media query, i.e. below xl, where the rail never mounts.
    renderPage();
    const heading = await screen.findByRole('heading', { name: 'The weekly newsletter' });
    expect(heading.closest('section')).toContainElement(screen.getByLabelText(/email address/i));
  });

  it('shows the newsletter signup only in the rail at xl (todo 409)', async () => {
    // The setup.ts polyfill matches nothing; stub the xl query, then restore.
    const originalMatchMedia = window.matchMedia;
    window.matchMedia = ((query: string) => ({
      matches: query === RAIL_MEDIA_QUERY,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    })) as unknown as typeof window.matchMedia;
    const rail = document.createElement('div');
    rail.id = RAIL_CONTAINER_ID;
    document.body.appendChild(rail);
    try {
      renderPage();
      const heading = await screen.findByRole('heading', { name: 'The weekly newsletter' });
      expect(rail).toContainElement(heading);
      // One form, not a second copy in the page.
      expect(screen.getAllByLabelText(/email address/i)).toHaveLength(1);
    } finally {
      window.matchMedia = originalMatchMedia;
      rail.remove();
    }
  });

  it('deep-links "Read the latest" to the newest post', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByRole('link', { name: 'Read the latest' })).toHaveAttribute(
        'href',
        '/blog/killed-by-kindness'
      );
    });
  });

  it('renders category chips and filters on click', async () => {
    renderPage();
    const chip = await screen.findByRole('button', { name: 'Care' });
    await userEvent.click(chip);
    await waitFor(() => {
      expect(mockFetchPosts).toHaveBeenCalledWith(
        expect.objectContaining({ category: 'care', page: 1 })
      );
    });
  });

  it('submits the search field into the query', async () => {
    renderPage();
    const input = await screen.findByRole('searchbox', { name: /search articles/i });
    await userEvent.type(input, 'mites{Enter}');
    await waitFor(() => {
      expect(mockFetchPosts).toHaveBeenCalledWith(
        expect.objectContaining({ search: 'mites', page: 1 })
      );
    });
  });

  it('renders the grid cards', async () => {
    renderPage();
    expect(await screen.findByText('Killed by kindness')).toBeInTheDocument();
  });

  it('shows an empty state with a clear-filters action when nothing matches', async () => {
    mockFetchPosts.mockResolvedValue({ items: [], meta: { total_count: 0 } });
    renderPage(['/blog?search=nomatch']);
    expect(await screen.findByText(/No articles found/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Clear all filters' })).toBeInTheDocument();
  });
});
