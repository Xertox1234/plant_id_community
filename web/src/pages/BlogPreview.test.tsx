import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import BlogPreview from './BlogPreview';
import { fetchBlogPreview } from '../services/blogService';
import { createMockBlogPost } from '@/tests/utils';

vi.mock('../services/blogService', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/blogService')>();
  return { ...actual, fetchBlogPreview: vi.fn() };
});
vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({ user: null, isAuthenticated: false, isLoading: false }),
}));

const mockFetchPreview = vi.mocked(fetchBlogPreview);

// The route shape Wagtail actually opens (wagtail-headless-preview 0.9 appends
// query parameters), mounted the way App.tsx mounts it.
function renderAt(url: string) {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <Routes>
        <Route path="/blog/preview" element={<BlogPreview />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('BlogPreview (web dead-code audit M2)', () => {
  beforeEach(() => {
    mockFetchPreview.mockReset();
  });

  it('fetches the draft named by the query parameters and renders it as an article', async () => {
    mockFetchPreview.mockResolvedValue(
      createMockBlogPost({ title: 'Draft about ferns', related_posts: [] })
    );

    renderAt('/blog/preview?content_type=blog.blogpostpage&token=abc%3A123');

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Draft about ferns' })
    ).toBeInTheDocument();
    expect(mockFetchPreview).toHaveBeenCalledWith('blog.blogpostpage', 'abc:123');
    expect(screen.getByRole('status')).toHaveTextContent(/not published/i);
    expect(screen.queryByText(/coming soon/i)).not.toBeInTheDocument();
    // Comments belong to the published post, not a draft.
    expect(screen.queryByRole('heading', { name: /comments/i })).not.toBeInTheDocument();
  });

  it('explains an expired or bad token instead of spinning', async () => {
    mockFetchPreview.mockRejectedValue(new Error('Preview not found or expired'));

    renderAt('/blog/preview?content_type=blog.blogpostpage&token=stale');

    expect(await screen.findByRole('alert')).toHaveTextContent('Preview not found or expired');
  });

  it('says the link is incomplete when a parameter is missing, without fetching', async () => {
    renderAt('/blog/preview?content_type=blog.blogpostpage');

    expect(await screen.findByRole('alert')).toHaveTextContent(/incomplete/i);
    expect(mockFetchPreview).not.toHaveBeenCalled();
  });
});
