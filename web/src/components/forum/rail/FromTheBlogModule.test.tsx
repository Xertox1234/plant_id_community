import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import FromTheBlogModule from './FromTheBlogModule';

const mockFetchPopularPosts = vi.fn();
vi.mock('../../../services/blogService', () => ({
  fetchPopularPosts: (...args: unknown[]) => mockFetchPopularPosts(...args),
}));

const post = (id: number, title: string, slug: string) => ({
  id,
  title,
  slug,
  meta: { slug, type: 'blog.BlogPage', detail_url: '', html_url: '', first_published_at: '' },
  content_blocks: [],
});

describe('FromTheBlogModule', () => {
  // NOTE (deviation from brief Step 1's exact snippet): braces, not an
  // implicit-return arrow body. `mockReset()` returns the mock itself (its
  // chaining API), so `beforeEach(() => mockFetchPopularPosts.mockReset())`
  // returns a function from the hook — Vitest treats a function returned
  // from `beforeEach` as a teardown callback and invokes it *after* the
  // test. That re-invokes the mock with no args, replaying whatever
  // implementation the test just set (e.g. a rejection), producing a real
  // unhandled rejection attributed to the test that just passed. Confirmed
  // via isolated repro outside this component/file entirely. A block body
  // avoids the implicit return; it's otherwise redundant with
  // vitest.config.ts's global `mockReset: true`, but kept for parity with
  // the brief's intent.
  beforeEach(() => {
    mockFetchPopularPosts.mockReset();
  });

  it('renders popular posts as links', async () => {
    mockFetchPopularPosts.mockResolvedValue([post(1, 'Monstera care', 'monstera-care')]);
    render(
      <MemoryRouter>
        <FromTheBlogModule />
      </MemoryRouter>
    );
    const link = await screen.findByRole('link', { name: /monstera care/i });
    expect(link).toHaveAttribute('href', '/blog/monstera-care');
    expect(screen.getByText('From the blog')).toBeInTheDocument();
  });

  it('renders nothing when there are no posts', async () => {
    mockFetchPopularPosts.mockResolvedValue([]);
    const { container } = render(
      <MemoryRouter>
        <FromTheBlogModule />
      </MemoryRouter>
    );
    await waitFor(() => expect(mockFetchPopularPosts).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing on fetch error', async () => {
    mockFetchPopularPosts.mockRejectedValue(new Error('nope'));
    const { container } = render(
      <MemoryRouter>
        <FromTheBlogModule />
      </MemoryRouter>
    );
    await waitFor(() => expect(mockFetchPopularPosts).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });
});
