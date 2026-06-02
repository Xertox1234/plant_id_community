import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import ThemePreviewPage from './ThemePreviewPage';

describe('ThemePreviewPage', () => {
  it('renders all 24 palette × density × mode combinations', () => {
    render(<ThemePreviewPage />);
    expect(screen.getAllByTestId('combo-card')).toHaveLength(24); // 4 × 3 × 2
  });
});
