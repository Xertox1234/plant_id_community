import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import Card from './Card';

describe('Card', () => {
  it('renders children on the gradient surface class', () => {
    render(<Card data-testid="c">hello</Card>);
    const el = screen.getByTestId('c');
    expect(el).toHaveTextContent('hello');
    expect(el.className).toContain('canopy-card');
    expect(el.className).not.toContain('canopy-interactive');
  });
  it('interactive adds the hover-lift class', () => {
    render(<Card data-testid="c" interactive />);
    expect(screen.getByTestId('c').className).toContain('canopy-interactive');
  });
  it('defaults to the md radius', () => {
    render(<Card data-testid="c" />);
    expect(screen.getByTestId('c').className).toContain('rounded-md');
  });
  it('radius is a prop, so no second rounded-* utility ever stacks on the element', () => {
    render(<Card data-testid="c" radius="lg" />);
    const cls = screen.getByTestId('c').className;
    expect(cls).toContain('rounded-lg');
    expect(cls).not.toContain('rounded-md');
  });
});
