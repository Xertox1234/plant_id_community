// web/src/components/ui/GrainOverlay.test.tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import GrainOverlay from './GrainOverlay';

describe('GrainOverlay', () => {
  it('renders children', () => {
    render(
      <GrainOverlay>
        <p>content</p>
      </GrainOverlay>
    );
    expect(screen.getByText('content')).toBeInTheDocument();
  });
  it('renders a non-interactive, aria-hidden overlay', () => {
    render(
      <GrainOverlay>
        <p>x</p>
      </GrainOverlay>
    );
    const overlay = screen.getByTestId('grain-overlay');
    expect(overlay).toHaveAttribute('aria-hidden', 'true');
    expect(overlay).toHaveClass('pointer-events-none');
  });
});
