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
    const bar = screen.getByRole('progressbar', { name: 'x' });
    const fill = bar.firstElementChild as HTMLElement;
    expect(fill.style.width).toBe('100%');
    expect(bar).toHaveAttribute('aria-valuenow', '50');
  });
  it('clamps negative values to 0%', () => {
    render(<ProgressBar value={-10} max={50} label="y" />);
    const bar = screen.getByRole('progressbar', { name: 'y' });
    const fill = bar.firstElementChild as HTMLElement;
    expect(fill.style.width).toBe('0%');
    expect(bar).toHaveAttribute('aria-valuenow', '0');
  });
});
