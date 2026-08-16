import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import BlogCard from './BlogCard';
import type { BlogPost } from '@/types';

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
  excerpt: 'Most houseplants don’t die of neglect.',
  content_blocks: [],
  featured_image: { url: '/media/cover-800.webp', width: 800, height: 400, alt: '' },
  featured_image_thumb: { url: '/media/cover-300.webp', width: 300, height: 200, alt: '' },
  publish_date: '2026-08-13',
  author: { id: 2, username: 'june_park', display_name: 'June Park' },
  categories: [{ id: 1, name: 'Care', slug: 'care' }],
  reading_time: 3,
};

function renderCard(p: BlogPost, compact = false) {
  return render(
    <MemoryRouter>
      <BlogCard post={p} compact={compact} />
    </MemoryRouter>
  );
}

describe('BlogCard', () => {
  it('links to the post detail page', () => {
    renderCard(post);
    expect(screen.getByRole('link')).toHaveAttribute('href', '/blog/killed-by-kindness');
  });

  it('renders title, category label, excerpt, and the meta line', () => {
    renderCard(post);
    expect(screen.getByText('Killed by kindness')).toBeInTheDocument();
    expect(screen.getByText('Care')).toBeInTheDocument();
    expect(screen.getByText(/die of neglect/)).toBeInTheDocument();
    // Meta line: "N min read · Author" (artifact card format). Key-PRESENCE
    // discipline: assert the whole joined string so a silently-missing
    // reading_time or author fails loudly.
    expect(screen.getByText('3 min read · June Park')).toBeInTheDocument();
  });

  it('uses the 800x400 rendition for the grid cover, resolved against the API origin', () => {
    const { container } = renderCard(post);
    // The cover is decorative (alt="" aria-hidden="true") — the visible
    // title text already carries the link's accessible name, so this is
    // queried by DOM structure rather than role. mediaUrl resolves the
    // relative rendition path against the API origin (no VITE_API_URL in
    // tests, so it falls back to http://localhost:8000).
    expect(container.querySelector('img')).toHaveAttribute(
      'src',
      'http://localhost:8000/media/cover-800.webp'
    );
  });

  it('passes a non-media absolute image url through unchanged', () => {
    const { container } = renderCard({
      ...post,
      featured_image: {
        url: 'https://cdn.example.com/assets/cover-800.webp',
        width: 800,
        height: 400,
        alt: '',
      },
    });
    expect(container.querySelector('img')).toHaveAttribute(
      'src',
      'https://cdn.example.com/assets/cover-800.webp'
    );
  });

  it('re-bases an absolute /media/ url onto the API origin (Site-record host is not trustworthy)', () => {
    const { container } = renderCard({
      ...post,
      // Live-probed shape: get_full_url resolves Wagtail's uncurated Site
      // record, not the API's actual host/port.
      featured_image: {
        url: 'http://localhost/media/cover-800.webp',
        width: 800,
        height: 400,
        alt: '',
      },
    });
    expect(container.querySelector('img')).toHaveAttribute(
      'src',
      'http://localhost:8000/media/cover-800.webp'
    );
  });

  it('omits the meta segments that are absent instead of printing blanks', () => {
    renderCard({ ...post, reading_time: null, author: undefined });
    expect(screen.queryByText(/min read/)).not.toBeInTheDocument();
    expect(screen.queryByText(/·/)).not.toBeInTheDocument();
  });

  it('renders without a cover when no image exists', () => {
    const { container } = renderCard({
      ...post,
      featured_image: undefined,
      featured_image_thumb: undefined,
    });
    expect(container.querySelector('img')).not.toBeInTheDocument();
    expect(screen.getByText('Killed by kindness')).toBeInTheDocument();
  });

  it('compact variant renders the 300x200 thumb and meta, no excerpt', () => {
    const { container } = renderCard(post, true);
    expect(container.querySelector('img')).toHaveAttribute(
      'src',
      'http://localhost:8000/media/cover-300.webp'
    );
    expect(screen.getByText('3 min read · June Park')).toBeInTheDocument();
    expect(screen.queryByText(/die of neglect/)).not.toBeInTheDocument();
  });
});
