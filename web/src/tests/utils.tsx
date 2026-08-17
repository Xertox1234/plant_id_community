/**
 * Test Utilities
 *
 * Provides common test utilities for React component testing.
 * Includes wrapper components for rendering with React Router and Auth context.
 */

import { render } from '@testing-library/react';
import type { ReactElement } from 'react';
import type { RenderOptions } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { AuthProvider } from '../contexts/AuthContext';
import { ThemeProvider } from '../contexts/ThemeContext';
import type { BlogPost, StreamFieldBlock } from '@/types/blog';

/**
 * Renders a component with React Router and Auth context.
 * Use this for components that need routing or authentication.
 */
export function renderWithRouter(ui: ReactElement, options: Omit<RenderOptions, 'wrapper'> = {}) {
  return render(
    <ThemeProvider>
      <BrowserRouter>
        <AuthProvider>{ui}</AuthProvider>
      </BrowserRouter>
    </ThemeProvider>,
    options
  );
}

/**
 * Renders a component with only React Router (no Auth context).
 * Use this for components that don't need authentication.
 */
export function renderWithRouterOnly(
  ui: ReactElement,
  options: Omit<RenderOptions, 'wrapper'> = {}
) {
  return render(<BrowserRouter>{ui}</BrowserRouter>, options);
}

/**
 * Creates a mock blog post object for testing (current Canopy `BlogPost`
 * shape). Single source of truth so a required-field change (e.g.
 * `featured_image_thumb`/`reading_time`/typed `author`) is fixed in one
 * place instead of drifting across BlogCard/BlogDetailPage/BlogListPage
 * test files (PR #540 review finding #6).
 */
export function createMockBlogPost(overrides: Partial<BlogPost> = {}): BlogPost {
  return {
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
    ...overrides,
  };
}

/**
 * Creates mock StreamField blocks for testing.
 */
export function createMockStreamBlocks(): StreamFieldBlock[] {
  return [
    {
      id: '1',
      type: 'heading',
      value: 'Test Heading',
    },
    {
      id: '2',
      type: 'paragraph',
      value: '<p>Test paragraph content</p>',
    },
    {
      id: '3',
      type: 'quote',
      value: {
        quote: 'Test quote',
        attribution: 'Test Author',
      },
    },
  ];
}
