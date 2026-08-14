import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import ProgressBar from './ProgressBar';

describe('ProgressBar', () => {
  it('exposes progressbar semantics', () => {
    render(<ProgressBar value={34} max={50} label="Progress to Botanist badge" />);
    const bar = screen.getByRole('progressbar', { name: 'Progress to Botanist badge' });
    expect(bar).toHaveAttribute('aria-valuenow', '34');
    expect(bar).toHaveAttribute('aria-valuemax', '50');
  });
  it('clamps overflow to 100%', () => {
    render(<ProgressBar value={80} max={50} label="x" />);
    const fill = screen.getByRole('progressbar', { name: 'x' }).firstElementChild as HTMLElement;
    expect(fill.style.width).toBe('100%');
  });
});
