import { useState, useCallback, useEffect, useRef } from 'react';
import { ChartBar, Check } from 'lucide-react';
import Button from '../ui/Button';
import { ForumApiError } from '../../services/forumService';
import type { ThreadPoll } from '@/types';

interface PollCardProps {
  poll: ThreadPoll;
  /** Cast a ballot (1..max_choices option ids). Resolves with the poll as
   * the SERVER recomputed it. */
  onVote: (optionIds: number[]) => Promise<ThreadPoll>;
  /** Signed-out viewers see results but get no vote controls. */
  canVote: boolean;
}

/** Whole-number percent of the total, or 0 when nobody has voted. */
function percent(count: number, total: number): number {
  if (total <= 0) return 0;
  return Math.round((count / total) * 100);
}

/**
 * PollCard Component
 *
 * Renders a thread's poll (audit M8): the question, the options, and — once
 * the viewer has voted, or the poll has closed — a result bar per option.
 *
 * Single-choice polls (`max_choices === 1`) vote with one click per option.
 * Multi-choice polls (todo 349) collect a ballot of checkboxes, capped at
 * `max_choices`, and submit it with one Vote button — the server takes the
 * whole ballot or refuses it, so there is no partial state to reconcile.
 *
 * Every number here comes from the server. The component never increments a
 * count locally: a vote resolves with the recomputed poll and that REPLACES
 * local state, so what a member sees always matches the rows behind it.
 *
 * Results are hidden until the viewer votes (or the poll closes) so the
 * running tally cannot anchor their choice. The total is shown throughout,
 * because "how many have answered" is not itself a nudge toward an option.
 * In a multi-choice poll that total is VOTERS, and the per-option counts can
 * sum past it — each bar is "share of voters who picked this".
 */
export default function PollCard({ poll, onVote, canVote }: PollCardProps) {
  const [current, setCurrent] = useState<ThreadPoll>(poll);
  // The ballot in flight, or null. Doubles as the single-choice loading
  // indicator (which button spins) and the in-flight guard for both kinds.
  const [pending, setPending] = useState<number[] | null>(null);
  // Multi-choice draft: the option ids ticked but not yet submitted.
  const [selected, setSelected] = useState<number[]>([]);
  const [error, setError] = useState<string | null>(null);
  // Set on a 409: the server says this viewer already voted, but `current`
  // (seeded from a possibly-stale `poll` prop — another tab, a bfcache
  // restore) still shows an empty my_vote_option_ids. Without this, the
  // controls stay clickable and every retry 409s again with no way out.
  const [staleVote, setStaleVote] = useState(false);

  // Resync when the `poll` PROP changes identity (a parent refetch — e.g.
  // ThreadDetailPage bumping `reloadKey` after a block/unblock action).
  // `key={thread.poll.id}` only remounts this component on cross-thread
  // navigation, not a same-thread refetch where `poll.id` is unchanged, so
  // without this a stale local `current` would keep showing pre-refetch
  // counts (todo 320 #2). Tracks the prop via a ref rather than depending on
  // `current` itself — including `current` in the deps would re-fire this
  // effect every time `handleVote` below sets it, immediately overwriting a
  // just-applied vote result with the (still pre-vote) `poll` prop. Skipped
  // entirely while a vote is in flight so a mid-request refetch can't race
  // the response that's about to replace `current` anyway.
  const pollRef = useRef(poll);
  useEffect(() => {
    if (poll !== pollRef.current) {
      pollRef.current = poll;
      if (pending === null) {
        setCurrent(poll);
      }
    }
  }, [poll, pending]);

  const isMulti = current.max_choices > 1;
  const hasVoted = current.my_vote_option_ids.length > 0;
  // A second submission is rejected server-side (409), never replaced — so
  // once the viewer has voted the controls are done, not merely busy.
  // `staleVote` does NOT feed this: `current` still shows 0 (or pre-vote)
  // counts, and switching to the results view would render those stale
  // numbers as if they were authoritative. Keep the controls in place, just
  // disabled — the alert explains why — rather than fabricating a results
  // panel from data that was never refetched.
  const showResults = hasVoted || current.is_closed;
  const votingDisabled = !canVote || hasVoted || current.is_closed || staleVote;
  const inFlight = pending !== null;

  const handleVote = useCallback(
    async (optionIds: number[]) => {
      if (votingDisabled || inFlight || optionIds.length === 0) return;
      setPending(optionIds);
      setError(null);
      try {
        // Not optimistic, deliberately: the counts are shared state every
        // reader sees, and the server can legitimately refuse (409 on a
        // second vote or a poll that closed while the page was open). Showing
        // a count that then has to be walked back is worse than a brief wait.
        setCurrent(await onVote(optionIds));
      } catch (err) {
        if (err instanceof ForumApiError && err.status === 409) {
          // Branch on the STATUS, never the message text (see
          // EditHistoryDialog's identical discipline) — a stale local
          // my_vote_option_ids can't be corrected without a refetch this
          // component doesn't have, so stop offering a retry that can only
          // ever 409 again.
          setStaleVote(true);
          setError("You've already voted in this poll — refresh to see your choice.");
        } else {
          setError(err instanceof Error ? err.message : 'Failed to record your vote');
        }
      } finally {
        setPending(null);
      }
    },
    [onVote, votingDisabled, inFlight]
  );

  const toggleSelected = (optionId: number) => {
    setSelected((prev) =>
      prev.includes(optionId)
        ? prev.filter((id) => id !== optionId)
        : prev.length < current.max_choices
          ? [...prev, optionId]
          : prev
    );
  };

  const totalNoun = isMulti
    ? current.total_votes === 1
      ? 'voter'
      : 'voters'
    : current.total_votes === 1
      ? 'vote'
      : 'votes';

  return (
    <section
      className="mb-6 rounded-md border border-line bg-surface-2 p-4"
      aria-labelledby={`poll-question-${current.id}`}
    >
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h2
          id={`poll-question-${current.id}`}
          className="gt-h3 inline-flex items-center gap-2 text-ink"
        >
          <ChartBar className="h-4 w-4 shrink-0 text-secondary" aria-hidden="true" />
          {current.question}
        </h2>
        {current.is_closed && (
          <span className="rounded-xs bg-surface-3 px-2 py-1 text-xs font-semibold text-ink-2">
            Closed
          </span>
        )}
      </div>

      {isMulti && !showResults && (
        <p id={`poll-cap-${current.id}`} className="mb-2 text-sm text-ink-2">
          Pick up to {current.max_choices}.
        </p>
      )}

      <ul className="space-y-2">
        {current.options.map((option) => {
          const share = percent(option.vote_count, current.total_votes);
          const isMine = current.my_vote_option_ids.includes(option.id);
          const isSelected = selected.includes(option.id);
          const capped = !isSelected && selected.length >= current.max_choices;
          return (
            <li key={option.id}>
              {showResults ? (
                <div className="rounded-sm border border-line bg-surface p-2">
                  <div className="flex items-baseline justify-between gap-2 text-sm">
                    <span className="font-medium text-ink">
                      {option.text}
                      {isMine && (
                        <span className="ml-2 inline-flex items-center gap-1 text-xs font-normal text-primary">
                          <Check className="h-3 w-3" aria-hidden="true" />
                          your vote
                        </span>
                      )}
                    </span>
                    <span className="text-ink-2">
                      {option.vote_count} ({share}%)
                    </span>
                  </div>
                  {/* The bar is decorative — the numbers beside it already
                      carry the value, and a progressbar role per option would
                      make a screen reader announce every row twice. */}
                  <div
                    className="mt-2 h-2 overflow-hidden rounded-pill bg-surface-3"
                    aria-hidden="true"
                  >
                    <div className="h-full bg-primary" style={{ width: `${share}%` }} />
                  </div>
                </div>
              ) : isMulti ? (
                <label
                  className={`flex min-h-11 cursor-pointer items-center gap-3 rounded-sm border border-line bg-surface px-3 py-2 text-sm text-ink has-[:disabled]:cursor-not-allowed has-[:disabled]:opacity-60 ${
                    capped ? 'opacity-60' : ''
                  }`}
                >
                  <input
                    type="checkbox"
                    className="h-4 w-4"
                    checked={isSelected}
                    // The cap is enforced here, not only server-side: an
                    // unticked box goes inert once the ballot is full, so
                    // the Vote button can never send a ballot the server
                    // would refuse whole. aria-disabled + a no-op rather
                    // than `disabled`, so the capped box stays in the tab
                    // order and a screen reader hears WHY (the cap hint is
                    // its description) instead of the option vanishing.
                    onChange={() => {
                      if (!capped) toggleSelected(option.id);
                    }}
                    aria-disabled={capped || undefined}
                    aria-describedby={`poll-cap-${current.id}`}
                    disabled={votingDisabled || inFlight}
                  />
                  {option.text}
                </label>
              ) : (
                <Button
                  onClick={() => handleVote([option.id])}
                  variant="outline"
                  disabled={votingDisabled || inFlight}
                  loading={pending?.includes(option.id) ?? false}
                  className="min-h-11 w-full justify-start text-left"
                >
                  {option.text}
                </Button>
              )}
            </li>
          );
        })}
      </ul>

      {isMulti && !showResults && (
        <Button
          onClick={() => handleVote(selected)}
          variant="primary"
          disabled={votingDisabled || inFlight || selected.length === 0}
          loading={inFlight}
          className="mt-3 min-h-11"
        >
          Vote
        </Button>
      )}

      <p className="mt-3 text-sm text-ink-2">
        {current.total_votes} {totalNoun}
        {!canVote && !current.is_closed && ' · sign in to vote'}
        {canVote && hasVoted && ' · your vote is final'}
      </p>

      {/* Always-mounted live region: a conditionally-rendered role node is
          generally NOT announced when it appears. Visually collapsed when
          empty, and its ancestors are all unconditional. */}
      <p role="alert" aria-live="polite" className={error ? 'mt-2 text-sm text-error' : 'sr-only'}>
        {error ?? ''}
      </p>
    </section>
  );
}
