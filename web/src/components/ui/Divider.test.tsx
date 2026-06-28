import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import Divider from './Divider';

describe('Divider', () => {
  it('renders the centered label when provided', () => {
    render(<Divider label="or" />);

    expect(screen.getByText('or')).toBeInTheDocument();
  });

  it('renders a bare line with no label text when label is omitted', () => {
    const { container } = render(<Divider />);

    // No label span, but the decorative line is still present.
    expect(container.querySelector('span')).toBeNull();
    expect(container.querySelector('.bg-line')).not.toBeNull();
  });
});
