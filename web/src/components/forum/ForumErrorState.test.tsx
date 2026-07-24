import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ForumErrorState from './ForumErrorState';

describe('ForumErrorState', () => {
  it('renders the title and message', () => {
    render(<ForumErrorState title="Error loading board" message="Boom" onRetry={() => {}} />);
    expect(screen.getByText(/Error loading board/i)).toBeInTheDocument();
    expect(screen.getByText('Boom')).toBeInTheDocument();
  });

  it('defaults the title to "Error"', () => {
    render(<ForumErrorState message="Boom" onRetry={() => {}} />);
    expect(screen.getByText(/^Error:/)).toBeInTheDocument();
  });

  it('invokes onRetry when Retry is clicked', async () => {
    const onRetry = vi.fn();
    render(<ForumErrorState message="Boom" onRetry={onRetry} />);

    await userEvent.click(screen.getByRole('button', { name: /retry/i }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
