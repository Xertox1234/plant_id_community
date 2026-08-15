import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import Avatar from './Avatar';

describe('Avatar', () => {
  it('renders the image with alt text', () => {
    render(<Avatar src="/avatars/specimen-1.jpg" alt="Iris Delgado" />);
    expect(screen.getByRole('img', { name: 'Iris Delgado' })).toBeInTheDocument();
  });
  it('shows a presence dot when online', () => {
    const { container } = render(<Avatar src="/a.jpg" alt="x" presence />);
    expect(container.querySelector('[data-presence]')).not.toBeNull();
  });
});
