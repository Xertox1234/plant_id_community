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
  it('wraps content in a GrainOverlay', () => {
    renderHome();
    expect(screen.getByTestId('grain-overlay')).toBeInTheDocument();
  });
  it('renders a ClayButton CTA (pill, clay)', () => {
    renderHome();
    // the primary CTA button — match by its label text
    const cta = screen.getByRole('button', { name: /get started|identify/i });
    expect(cta).toHaveClass('rounded-pill');
    expect(cta).toHaveClass('bg-clay');
  });
});
