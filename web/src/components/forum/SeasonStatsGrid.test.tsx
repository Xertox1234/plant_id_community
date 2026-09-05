import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import SeasonStatsGrid from './SeasonStatsGrid';
import type { ForumMyStats } from '../../types/forum';

function makeMyStats(overrides: Partial<ForumMyStats> = {}): ForumMyStats {
  return {
    posts: 12,
    solutions_accepted: 3,
    identifications_shared: 7,
    streak_days: 4,
    badge_name: 'Botanist',
    badge_progress: 7,
    badge_target: 20,
    badges: [],
    ...overrides,
  };
}

describe('SeasonStatsGrid', () => {
  it('renders all four stat values with their labels', () => {
    render(<SeasonStatsGrid stats={makeMyStats()} />);

    expect(screen.getByText('Identifications')).toBeInTheDocument();
    expect(screen.getByText('7')).toBeInTheDocument();
    expect(screen.getByText('Posts')).toBeInTheDocument();
    expect(screen.getByText('12')).toBeInTheDocument();
    expect(screen.getByText('Solutions')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByText('Day streak')).toBeInTheDocument();
    expect(screen.getByText('4')).toBeInTheDocument();
  });

  it('shows remaining-to-badge while below target, and the badge progress bar', () => {
    render(<SeasonStatsGrid stats={makeMyStats({ badge_progress: 7, badge_target: 20 })} />);

    expect(screen.getByText('13 to Botanist badge')).toBeInTheDocument();
    const bar = screen.getByRole('progressbar', { name: 'Botanist badge progress' });
    expect(bar).toHaveAttribute('aria-valuenow', '7');
    expect(bar).toHaveAttribute('aria-valuemax', '20');
  });

  it('shows badge complete once progress reaches the target', () => {
    render(<SeasonStatsGrid stats={makeMyStats({ badge_progress: 20, badge_target: 20 })} />);

    expect(screen.getByText('Botanist badge complete')).toBeInTheDocument();
    expect(screen.queryByText(/to Botanist badge$/)).not.toBeInTheDocument();
  });

  it('pluralises the streak sublabel and prompts at zero', () => {
    const { unmount } = render(<SeasonStatsGrid stats={makeMyStats({ streak_days: 0 })} />);
    expect(screen.getByText('Post to start a streak')).toBeInTheDocument();
    unmount();

    const single = render(<SeasonStatsGrid stats={makeMyStats({ streak_days: 1 })} />);
    expect(screen.getByText('day in a row')).toBeInTheDocument();
    single.unmount();

    render(<SeasonStatsGrid stats={makeMyStats({ streak_days: 5 })} />);
    expect(screen.getByText('days in a row')).toBeInTheDocument();
  });

  it('appends the caller-supplied className to the grid wrapper', () => {
    const { container } = render(<SeasonStatsGrid stats={makeMyStats()} className="mt-6" />);
    const grid = container.querySelector('.grid');
    expect(grid).toHaveClass('mt-6');
    expect(grid).toHaveClass('lg:grid-cols-4');
  });
});
