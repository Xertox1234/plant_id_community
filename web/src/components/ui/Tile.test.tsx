import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import Tile from './Tile';
import { TILE_BOX, TILE_RADIUS } from './dimensions';

describe('Tile', () => {
  it('paints the tone gradient token', () => {
    render(<Tile tone="pollen" data-testid="t" />);
    expect(screen.getByTestId('t')).toHaveStyle({ background: 'var(--gt-tile-pollen)' });
  });
  it('defaults to sage', () => {
    render(<Tile data-testid="t" />);
    expect(screen.getByTestId('t')).toHaveStyle({ background: 'var(--gt-tile-sage)' });
  });
  it('takes its box and radius from the shared dimension table', () => {
    render(<Tile size="md" data-testid="t" />);
    const cls = screen.getByTestId('t').className;
    expect(cls).toContain(TILE_BOX.md);
    expect(cls).toContain(TILE_RADIUS.md);
  });
});
