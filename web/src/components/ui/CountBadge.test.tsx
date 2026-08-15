import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import CountBadge from './CountBadge';

describe('CountBadge', () => {
  it('renders the count', () => {
    render(<CountBadge count={4} />);
    expect(screen.getByText('4')).toBeInTheDocument();
  });
  it('caps at max with a plus', () => {
    render(<CountBadge count={120} />);
    expect(screen.getByText('99+')).toBeInTheDocument();
  });
  it('renders nothing at zero', () => {
    const { container } = render(<CountBadge count={0} />);
    expect(container).toBeEmptyDOMElement();
  });
});
