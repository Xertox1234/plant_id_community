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
import type { StreamFieldBlock } from '@/types/blog';

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
