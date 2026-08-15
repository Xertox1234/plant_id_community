import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { ReactElement } from 'react';
import ButtonLink from './ButtonLink';

const renderLink = (ui: ReactElement) => render(<MemoryRouter>{ui}</MemoryRouter>);

describe('ButtonLink', () => {
  it('renders a real link with the target href and no nested button', () => {
    renderLink(<ButtonLink to="/forum/new-thread">Start a thread</ButtonLink>);
    const link = screen.getByRole('link', { name: 'Start a thread' });
    expect(link).toHaveAttribute('href', '/forum/new-thread');
    expect(link.querySelector('button')).toBeNull();
  });

  it('defaults to the primary variant', () => {
    renderLink(<ButtonLink to="/x">go</ButtonLink>);
    expect(screen.getByRole('link', { name: 'go' })).toHaveClass('canopy-cta');
  });

  it('wears the Button recipe for its variant, size, and extra classes', () => {
    renderLink(
      <ButtonLink to="/x" variant="ghost" size="sm" className="min-h-11">
        go
      </ButtonLink>
    );
    const link = screen.getByRole('link', { name: 'go' });
    expect(link).toHaveClass('rounded-pill');
    expect(link).toHaveClass('hover:bg-surface-2');
    expect(link).toHaveClass('px-3');
    expect(link).toHaveClass('min-h-11');
    // The design system's only keyboard-focus treatment must survive on links.
    expect(link).toHaveClass('focus-visible:ring-2');
  });
});
