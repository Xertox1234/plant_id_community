// web/src/pages/HomePage.test.tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import HomePage from './HomePage';

const renderHome = () =>
  render(
    <BrowserRouter>
      <HomePage />
    </BrowserRouter>
  );

describe('HomePage', () => {
  it('renders the hero headline and CTA links, not a GrainOverlay or ClayButton', () => {
    renderHome();
    expect(
      screen.getByRole('heading', { level: 2, name: /discover the world of plants/i })
    ).toBeInTheDocument();
    expect(screen.queryByTestId('grain-overlay')).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 1, name: 'Home' })).toHaveClass('sr-only');

    const getStarted = screen.getByRole('link', { name: /get started/i });
    expect(getStarted).toHaveAttribute('href', '/identify');
    const joinCommunity = screen.getByRole('link', { name: /join community/i });
    expect(joinCommunity).toHaveAttribute('href', '/forum');
  });

  it('renders the three feature cards as links to their pages', () => {
    renderHome();

    expect(screen.getByRole('link', { name: /ai plant identification/i })).toHaveAttribute(
      'href',
      '/identify'
    );
    expect(screen.getByRole('link', { name: /discussion forum/i })).toHaveAttribute(
      'href',
      '/forum'
    );
    expect(screen.getByRole('link', { name: /plant blog/i })).toHaveAttribute('href', '/blog');
  });
});
