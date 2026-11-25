import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import Tile from './Tile';
import { TILE_BOX, TILE_RADIUS } from './dimensions';

// The inline style is read directly: the token is not defined in a test
// document, and jsdom 30 computes an undefined var() in `background` to the
// initial value, so toHaveStyle (which reads the computed style) sees nothing.
describe('Tile', () => {
  it('paints the tone gradient token', () => {
    render(<Tile tone="pollen" data-testid="t" />);
    expect(screen.getByTestId('t').style.background).toBe('var(--gt-tile-pollen)');
  });
  it('defaults to sage', () => {
    render(<Tile data-testid="t" />);
    expect(screen.getByTestId('t').style.background).toBe('var(--gt-tile-sage)');
  });
  it('takes its box and radius from the shared dimension table', () => {
    render(<Tile size="md" data-testid="t" />);
    const cls = screen.getByTestId('t').className;
    expect(cls).toContain(TILE_BOX.md);
    expect(cls).toContain(TILE_RADIUS.md);
  });
});
