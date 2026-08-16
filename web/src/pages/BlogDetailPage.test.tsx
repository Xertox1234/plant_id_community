import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import BlogDetailPage from './BlogDetailPage';
import { fetchBlogPost } from '../services/blogService';
import type { BlogPost } from '@/types';

vi.mock('../services/blogService', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/blogService')>();
  return {
    ...actual,
    fetchBlogPost: vi.fn(),
  };
});

const mockFetchPost = vi.mocked(fetchBlogPost);

const post: BlogPost = {
  id: 1,
  meta: {
    type: 'blog.BlogPostPage',
    detail_url: '',
    html_url: '',
    slug: 'killed-by-kindness',
    first_published_at: '2026-08-13T09:00:00Z',
  },
  slug: 'killed-by-kindness',
  title: 'Killed by kindness',
  introduction: '<p>Most houseplants don’t die of neglect.</p>',
  content_blocks: [
    { type: 'heading', value: 'What overwatering actually is' },
    { type: 'paragraph', value: '<p>Roots respire.</p>' },
  ],
  featured_image: {
    url: '/media/cover-800.webp',
    width: 800,
    height: 400,
    alt: 'Overwatered pothos',
  },
  publish_date: '2026-08-13',
  author: { id: 2, username: 'june_park', display_name: 'June Park' },
  categories: [{ id: 1, name: 'Care', slug: 'care' }],
  reading_time: 3,
  related_posts: [
    {
      id: 2,
      title: 'Your fiddle leaf isn’t dying, it’s adjusting',
      slug: 'fiddle-leaf-adjusting',
      excerpt: 'Before you diagnose disease…',
      // Live-probed shape: _get_post_image's get_full_url resolves
      // Wagtail's uncurated Site record (port 80), not the API's actual
      // host — mediaUrl re-bases it onto the API origin regardless.
      featured_image: 'http://localhost/media/fiddle-300.webp',
    },
  ],
};

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/blog/killed-by-kindness']}>
      <Routes>
        <Route path="/blog/:slug" element={<BlogDetailPage />} />
      </Routes>
    </MemoryRouter>
  );
}

beforeEach(() => {
  mockFetchPost.mockResolvedValue(post);
});

describe('BlogDetailPage', () => {
  it('renders headline, eyebrow, author line, and cover', async () => {
    renderPage();
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Killed by kindness' })
    ).toBeInTheDocument();
    expect(screen.getByText('Care')).toBeInTheDocument();
    expect(screen.getByText(/August 13, 2026/)).toBeInTheDocument();
    // Key-presence discipline: the full joined line, so a silently-null
    // reading_time or author fails loudly.
    expect(screen.getByText('By June Park · 3 min read')).toBeInTheDocument();
    // featured_image.url is relative — resolved against the API origin by
    // mediaUrl (no VITE_API_URL in tests, so it falls back to
    // http://localhost:8000).
    expect(screen.getByAltText('Overwatered pothos')).toHaveAttribute(
      'src',
      'http://localhost:8000/media/cover-800.webp'
    );
  });

  it('renders the StreamField body', async () => {
    renderPage();
    expect(
      await screen.findByRole('heading', { name: 'What overwatering actually is' })
    ).toBeInTheDocument();
    expect(screen.getByText('Roots respire.')).toBeInTheDocument();
  });

  it('renders the related-posts strip with links', async () => {
    const { container } = renderPage();
    expect(await screen.findByText('More from the blog')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /fiddle leaf/i })).toHaveAttribute(
      'href',
      '/blog/fiddle-leaf-adjusting'
    );
    // related_posts[].featured_image is a plain URL string (not a rendition
    // object) — here the realistic Site-record-based absolute shape
    // (wrong host). mediaUrl re-bases it onto the API origin regardless.
    // Decorative, so queried by DOM structure.
    const relatedImg = container.querySelector('aside img');
    expect(relatedImg).toHaveAttribute('src', 'http://localhost:8000/media/fiddle-300.webp');
  });

  it('hides the related strip when the server sends none', async () => {
    mockFetchPost.mockResolvedValue({ ...post, related_posts: [] });
    renderPage();
    await screen.findByRole('heading', { level: 1, name: 'Killed by kindness' });
    expect(screen.queryByText('More from the blog')).not.toBeInTheDocument();
  });

  it('renders the 404 page for an unknown slug', async () => {
    mockFetchPost.mockRejectedValue(new Error('Blog post not found'));
    renderPage();
    expect(await screen.findByText('This leaf is not in our records.')).toBeInTheDocument();
  });
});
