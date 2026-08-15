import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Chip from './Chip';

describe('Chip', () => {
  it('reflects active state via aria-pressed and the CTA class', () => {
    render(<Chip active>All</Chip>);
    const b = screen.getByRole('button', { name: 'All' });
    expect(b).toHaveAttribute('aria-pressed', 'true');
    expect(b.className).toContain('canopy-cta');
  });
  it('inactive chip is pressable', async () => {
    const onClick = vi.fn();
    render(<Chip onClick={onClick}>Care</Chip>);
    const b = screen.getByRole('button', { name: 'Care' });
    expect(b).toHaveAttribute('aria-pressed', 'false');
    await userEvent.click(b);
    expect(onClick).toHaveBeenCalledOnce();
  });
});
