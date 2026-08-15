import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import Tile from './Tile';

describe('Tile', () => {
  it('paints the tone gradient token', () => {
    render(<Tile tone="pollen" data-testid="t" />);
    expect(screen.getByTestId('t')).toHaveStyle({ background: 'var(--gt-tile-pollen)' });
  });
  it('defaults to sage', () => {
    render(<Tile data-testid="t" />);
    expect(screen.getByTestId('t')).toHaveStyle({ background: 'var(--gt-tile-sage)' });
  });
});
