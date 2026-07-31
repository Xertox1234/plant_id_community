import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import PollCard from './PollCard';
import type { ThreadPoll } from '@/types';

function makePoll(overrides: Partial<ThreadPoll> = {}): ThreadPoll {
  return {
    id: 1,
    question: 'Best soil for aroids?',
    closes_at: null,
    is_closed: false,
    options: [
      { id: 10, text: 'Peat', order: 0, vote_count: 0 },
      { id: 11, text: 'Coir', order: 1, vote_count: 0 },
    ],
    total_votes: 0,
    my_vote_option_id: null,
    ...overrides,
  };
}

describe('PollCard', () => {
  it('renders the question and offers each option as a vote control', () => {
    render(<PollCard poll={makePoll()} onVote={vi.fn()} canVote />);

    expect(screen.getByRole('heading', { name: /Best soil for aroids/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Peat' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Coir' })).toBeInTheDocument();
  });

  it('hides results until the viewer has voted, so the tally cannot anchor them', () => {
    render(
      <PollCard
        poll={makePoll({
          total_votes: 50,
          options: [
            { id: 10, text: 'Peat', order: 0, vote_count: 49 },
            { id: 11, text: 'Coir', order: 1, vote_count: 1 },
          ],
        })}
        onVote={vi.fn()}
        canVote
      />
    );

    // The lopsided per-option counts are not on screen…
    expect(screen.queryByText(/49/)).not.toBeInTheDocument();
    expect(screen.queryByText(/98%/)).not.toBeInTheDocument();
    // …but "how many have answered" is, which is not itself a nudge.
    expect(screen.getByText(/50 votes/i)).toBeInTheDocument();
  });

  it('voting replaces local state with the SERVER-recomputed poll', async () => {
    // The count the client shows must come from the response, never from a
    // local increment — this poll comes back with 7, not 0+1.
    const onVote = vi.fn().mockResolvedValue(
      makePoll({
        total_votes: 7,
        my_vote_option_id: 10,
        options: [
          { id: 10, text: 'Peat', order: 0, vote_count: 5 },
          { id: 11, text: 'Coir', order: 1, vote_count: 2 },
        ],
      })
    );
    render(<PollCard poll={makePoll()} onVote={onVote} canVote />);

    await userEvent.click(screen.getByRole('button', { name: 'Peat' }));

    expect(onVote).toHaveBeenCalledWith(10);
    expect(await screen.findByText(/7 votes/i)).toBeInTheDocument();
    expect(screen.getByText('5 (71%)')).toBeInTheDocument();
    expect(screen.getByText('2 (29%)')).toBeInTheDocument();
    // Exact, not /your vote/i — that substring also matches the "your vote is
    // final" footer, so the loose regex finds two elements.
    expect(screen.getByText('✓ your vote')).toBeInTheDocument();
  });

  it('shows results and no vote controls once the viewer has voted', () => {
    render(
      <PollCard
        poll={makePoll({
          my_vote_option_id: 11,
          total_votes: 3,
          options: [
            { id: 10, text: 'Peat', order: 0, vote_count: 1 },
            { id: 11, text: 'Coir', order: 1, vote_count: 2 },
          ],
        })}
        onVote={vi.fn()}
        canVote
      />
    );

    expect(screen.queryByRole('button', { name: 'Peat' })).not.toBeInTheDocument();
    expect(screen.getByText('2 (67%)')).toBeInTheDocument();
    // A second vote is refused server-side, so the UI says so rather than
    // implying the choice can be changed.
    expect(screen.getByText(/your vote is final/i)).toBeInTheDocument();
  });

  it('surfaces a failed vote and leaves the controls usable', async () => {
    const onVote = vi.fn().mockRejectedValue(new Error('You have already voted in this poll.'));
    render(<PollCard poll={makePoll()} onVote={onVote} canVote />);

    await userEvent.click(screen.getByRole('button', { name: 'Peat' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/already voted/i);
    // No optimistic count was applied, so nothing needs walking back.
    expect(screen.getByText(/0 votes/i)).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Peat' })).not.toBeDisabled();
    });
  });

  it('mounts the error region empty rather than creating it on failure', () => {
    // A conditionally-rendered role node is generally not announced when it
    // appears; asserting it exists and is empty up front is what proves the
    // region is persistent (findByText after the fact passes either way).
    render(<PollCard poll={makePoll()} onVote={vi.fn()} canVote />);

    expect(screen.getByRole('alert')).toHaveTextContent('');
  });

  it('shows results but no vote controls to a signed-out viewer', () => {
    render(<PollCard poll={makePoll({ total_votes: 4 })} onVote={vi.fn()} canVote={false} />);

    expect(screen.queryByRole('button', { name: 'Peat' })).toBeDisabled();
    expect(screen.getByText(/sign in to vote/i)).toBeInTheDocument();
  });

  it('shows a closed poll with results and no vote controls', () => {
    render(
      <PollCard
        poll={makePoll({
          is_closed: true,
          closes_at: '2026-01-01T00:00:00Z',
          total_votes: 2,
          options: [
            { id: 10, text: 'Peat', order: 0, vote_count: 2 },
            { id: 11, text: 'Coir', order: 1, vote_count: 0 },
          ],
        })}
        onVote={vi.fn()}
        canVote
      />
    );

    expect(screen.getByText('Closed')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Peat' })).not.toBeInTheDocument();
    expect(screen.getByText('2 (100%)')).toBeInTheDocument();
  });

  it('renders 0% rather than dividing by zero when nobody has voted', () => {
    render(<PollCard poll={makePoll({ is_closed: true })} onVote={vi.fn()} canVote />);

    expect(screen.getAllByText('0 (0%)')).toHaveLength(2);
  });

  it('ignores a second click while a vote is in flight', async () => {
    let resolveVote: (poll: ThreadPoll) => void = () => {};
    const onVote = vi
      .fn()
      .mockImplementation(() => new Promise<ThreadPoll>((res) => (resolveVote = res)));
    render(<PollCard poll={makePoll()} onVote={onVote} canVote />);

    await userEvent.click(screen.getByRole('button', { name: 'Peat' }));
    await userEvent.click(screen.getByRole('button', { name: 'Coir' }));

    expect(onVote).toHaveBeenCalledTimes(1);
    resolveVote(makePoll({ my_vote_option_id: 10, total_votes: 1 }));
  });
});
