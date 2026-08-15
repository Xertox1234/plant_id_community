import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import ThemePreviewPage from './ThemePreviewPage';

describe('ThemePreviewPage', () => {
  it('renders all 6 density × mode combinations', () => {
    render(<ThemePreviewPage />);
    expect(screen.getAllByTestId('combo-card')).toHaveLength(6); // 3 × 2
  });
});
