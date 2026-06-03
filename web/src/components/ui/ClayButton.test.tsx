// web/src/components/ui/ClayButton.test.tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import ClayButton from './ClayButton';

describe('ClayButton', () => {
  it('renders the label', () => {
    render(<ClayButton label="Get Started" />);
    expect(screen.getByText('Get Started')).toBeInTheDocument();
  });
  it('primary variant uses clay background', () => {
    render(<ClayButton label="X" />);
    expect(screen.getByRole('button')).toHaveClass('bg-clay');
  });
  it('secondary variant uses primary background', () => {
    render(<ClayButton label="X" variant="secondary" />);
    expect(screen.getByRole('button')).toHaveClass('bg-primary');
  });
  it('outline variant is transparent with a primary border', () => {
    render(<ClayButton label="X" variant="outline" />);
    const btn = screen.getByRole('button');
    expect(btn).toHaveClass('bg-transparent');
    expect(btn).toHaveClass('border-primary');
  });
  it('disabled is non-interactive and dropped of shadow/clay', () => {
    render(<ClayButton label="X" disabled />);
    const btn = screen.getByRole('button');
    expect(btn).toBeDisabled();
    expect(btn).not.toHaveClass('shadow-2');
    expect(btn).not.toHaveClass('bg-clay');
  });
  it('fullWidth spans the container', () => {
    render(<ClayButton label="X" fullWidth />);
    expect(screen.getByRole('button')).toHaveClass('w-full');
  });
  it('renders a provided icon', () => {
    render(<ClayButton label="X" icon={<svg data-testid="ic" />} />);
    expect(screen.getByTestId('ic')).toBeInTheDocument();
  });
  it('loading shows a spinner, sets aria-busy, and keeps an accessible name', () => {
    render(<ClayButton label="X" loading />);
    const btn = screen.getByRole('button', { name: 'X' }); // accessible name preserved via sr-only
    expect(btn).toHaveAttribute('aria-busy', 'true');
    expect(btn).toBeDisabled();
    expect(btn.querySelector('.animate-spin')).toBeTruthy();
  });
  it('defaults to type="button" and allows override', () => {
    const { rerender } = render(<ClayButton label="A" />);
    expect(screen.getByRole('button')).toHaveAttribute('type', 'button');
    rerender(<ClayButton label="A" type="submit" />);
    expect(screen.getByRole('button')).toHaveAttribute('type', 'submit');
  });
  it('primary variant exposes hover and active feedback', () => {
    render(<ClayButton label="X" />);
    const btn = screen.getByRole('button');
    expect(btn).toHaveClass('hover:bg-clay/90');
    expect(btn).toHaveClass('active:translate-y-px');
  });
  it('disabled state drops the interactive affordances', () => {
    render(<ClayButton label="X" disabled />);
    const btn = screen.getByRole('button');
    expect(btn).not.toHaveClass('hover:bg-clay/90');
    expect(btn).not.toHaveClass('active:translate-y-px');
  });
});
