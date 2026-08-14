import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import HeroCard from './HeroCard';

describe('HeroCard', () => {
  it('renders eyebrow, heading, description, actions and art', () => {
    render(
      <HeroCard
        eyebrow="Community event"
        title="The bloom watch is on."
        description="Post yours, get it identified."
        actions={<button>Join</button>}
        art={<img src="/x.webp" alt="" data-testid="art" />}
      />
    );
    expect(screen.getByRole('heading', { name: 'The bloom watch is on.' })).toBeInTheDocument();
    expect(screen.getByText('Community event')).toBeInTheDocument();
    expect(screen.getByText('Post yours, get it identified.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Join' })).toBeInTheDocument();
    expect(screen.getByTestId('art')).toBeInTheDocument();
  });
});
