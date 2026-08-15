import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import BrandMark from './BrandMark';

describe('BrandMark', () => {
  it('renders an accessible Houseplant MD mark', () => {
    render(<BrandMark />);
    expect(screen.getByRole('img', { name: 'Houseplant MD' })).toBeInTheDocument();
  });
  it('two instances have no colliding gradient ids', () => {
    const { container } = render(
      <div>
        <BrandMark />
        <BrandMark />
      </div>
    );
    const ids = Array.from(container.querySelectorAll('linearGradient')).map((g) => g.id);
    expect(new Set(ids).size).toBe(ids.length);
  });
});
