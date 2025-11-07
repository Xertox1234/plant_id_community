/**
 * Test Utilities
 *
 * Provides common test utilities for React component testing.
 * Includes wrapper components for rendering with React Router and Auth context.
 */

import { render } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { AuthProvider } from '../contexts/AuthContext';

/**
 * Renders a component with React Router and Auth context.
 * Use this for components that need routing or authentication.
 *
 * @param {React.ReactElement} ui - Component to render
 * @param {Object} options - Render options
 * @returns {Object} Testing Library render result
 */
export function renderWithRouter(ui, options = {}) {
  return render(
    <BrowserRouter>
      <AuthProvider>
        {ui}
      </AuthProvider>
    </BrowserRouter>,
    options
  );
}

/**
 * Renders a component with only React Router (no Auth context).
 * Use this for components that don't need authentication.
 *
 * @param {React.ReactElement} ui - Component to render
 * @param {Object} options - Render options
 * @returns {Object} Testing Library render result
 */
export function renderWithRouterOnly(ui, options = {}) {
  return render(
    <BrowserRouter>
      {ui}
    </BrowserRouter>,
    options
  );
}

/**
 * Creates a mock blog post object for testing.
 *
 * @param {Object} overrides - Properties to override
 * @returns {Object} Mock blog post
 */
export function createMockBlogPost(overrides = {}) {
  return {
    slug: 'test-post',
    title: 'Test Blog Post',
    introduction: '<p>This is a test introduction</p>',
    publish_date: '2025-10-25T10:00:00Z',
    author: {
      first_name: 'John',
      last_name: 'Doe',
    },
    categories: [
      { name: 'Gardening' },
    ],
    tags: ['plants', 'care'],
    view_count: 100,
    featured_image: {
      url: 'https://example.com/image.jpg',
      title: 'Test Image',
      thumbnail: {
        url: 'https://example.com/thumbnail.jpg',
      },
    },
    ...overrides,
  };
}

/**
 * Creates mock StreamField blocks for testing.
 *
 * @returns {Array} Array of mock blocks
 */
export function createMockStreamBlocks() {
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
