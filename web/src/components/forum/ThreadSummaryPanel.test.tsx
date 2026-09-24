import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, fireEvent, render, screen } from '@testing-library/react';
import ThreadSummaryPanel from './ThreadSummaryPanel';
import * as forumService from '../../services/forumService';
import { logger } from '../../utils/logger';
import type { TopicSummary } from '../../types/forum';

/**
 * ThreadSummaryPanel (todo 414) — the premium "Summarize thread" button.
 *
 * The web has no client-side premium flag, so availability follows the
 * compose-assist contract: the server's 403 latches "this account can't" in the
 * service for the session (a remount on the next thread renders nothing); 429
 * is transient. A 202 `pending` is polled — sparingly, because every poll
 * spends the same 30/h bucket as a click.
 */

const READY: TopicSummary = {
  status: 'ready',
  summary: 'The thread settles on bottom-watering once a week.',
  post_count: 5,
  generated_at: '2026-09-24T10:00:00+00:00',
};
const PENDING: TopicSummary = { status: 'pending' };

const summarize = () => screen.getByRole('button', { name: /summarize thread/i });
const statusRegion = () => screen.getByRole('status');

/** Flush the awaited fetch + the next poll timer. */
async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

describe('ThreadSummaryPanel', () => {
  beforeEach(() => {
    // Session-scoped module latch — would otherwise leak from the 403 case.
    forumService.resetTopicSummaryAvailability();
    vi.spyOn(logger, 'error').mockImplementation(() => {});
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('runs a summary for the topic and renders it as text (premium path)', async () => {
    const fetchSummary = vi.spyOn(forumService, 'fetchTopicSummary').mockResolvedValue(READY);
    render(<ThreadSummaryPanel topicId={12} />);
    // Persistent live region: present and EMPTY before anything happens.
    expect(statusRegion()).toBeEmptyDOMElement();
    expect(fetchSummary).not.toHaveBeenCalled();

    fireEvent.click(summarize());
    await advance(0);

    expect(fetchSummary).toHaveBeenCalledWith(12, expect.any(AbortSignal));
    expect(screen.getByText(READY.summary)).toBeInTheDocument();
    expect(screen.getByText(/5 posts/)).toBeInTheDocument();
  });

  it('polls a 202 pending until the summary is ready', async () => {
    const fetchSummary = vi
      .spyOn(forumService, 'fetchTopicSummary')
      .mockResolvedValueOnce(PENDING)
      .mockResolvedValueOnce(READY);
    render(<ThreadSummaryPanel topicId={12} />);

    fireEvent.click(summarize());
    await advance(0);
    expect(fetchSummary).toHaveBeenCalledTimes(1);
    // Loading while pending (Button swaps in its loadingText label).
    expect(screen.getByRole('button', { name: /summarizing/i })).toBeDisabled();

    await advance(5000);
    expect(fetchSummary).toHaveBeenCalledTimes(2);
    expect(screen.getByText(READY.summary)).toBeInTheDocument();
  });

  it('stops polling after a bounded number of attempts and says to come back', async () => {
    const fetchSummary = vi.spyOn(forumService, 'fetchTopicSummary').mockResolvedValue(PENDING);
    render(<ThreadSummaryPanel topicId={12} />);

    fireEvent.click(summarize());
    await advance(60_000);

    // 1 initial request + 6 polls — never an open-ended loop against a 30/h bucket.
    expect(fetchSummary).toHaveBeenCalledTimes(7);
    expect(statusRegion()).toHaveTextContent(/still being written/i);
    expect(summarize()).toBeEnabled();
  });

  it('shows the throttled message on 429 and keeps the button for later', async () => {
    vi.spyOn(forumService, 'fetchTopicSummary').mockRejectedValue(
      new forumService.TopicSummaryError(
        429,
        'Rate limit exceeded. Please try again later.',
        'rate_limit_exceeded',
        3600
      )
    );
    render(<ThreadSummaryPanel topicId={12} />);

    fireEvent.click(summarize());
    await advance(0);

    expect(statusRegion()).toHaveTextContent(/summary limit.*about 60 minutes/i);
    expect(summarize()).toBeEnabled();
    expect(forumService.isTopicSummaryUnavailable()).toBe(false);
  });

  it('on 403 (not premium) hides the button, shows the premium notice, and latches', async () => {
    vi.spyOn(forumService, 'fetchTopicSummary').mockRejectedValue(
      new forumService.TopicSummaryError(403, 'This feature requires a premium account.')
    );
    const { unmount } = render(<ThreadSummaryPanel topicId={12} />);

    fireEvent.click(summarize());
    await advance(0);

    expect(statusRegion()).toHaveTextContent('This feature requires a premium account.');
    expect(screen.queryByRole('button', { name: /summarize thread/i })).not.toBeInTheDocument();
    expect(forumService.isTopicSummaryUnavailable()).toBe(true);

    // The next thread (a remount) must not re-offer it: a non-premium user sees nothing.
    unmount();
    const { container } = render(<ThreadSummaryPanel topicId={13} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('says a too-short thread cannot be summarized yet', async () => {
    vi.spyOn(forumService, 'fetchTopicSummary').mockResolvedValue({
      status: 'too_short',
      post_count: 2,
    });
    render(<ThreadSummaryPanel topicId={12} />);

    fireEvent.click(summarize());
    await advance(0);

    expect(screen.getByText(/at least 3 posts/i)).toBeInTheDocument();
  });

  it('shows a generic error for other failures and keeps the button', async () => {
    vi.spyOn(forumService, 'fetchTopicSummary').mockRejectedValue(
      new forumService.TopicSummaryError(500, 'Internal server error')
    );
    render(<ThreadSummaryPanel topicId={12} />);

    fireEvent.click(summarize());
    await advance(0);

    expect(statusRegion()).toHaveTextContent(/couldn.t summarize this thread/i);
    expect(summarize()).toBeEnabled();
  });

  it('stops polling when unmounted (navigating away mid-generation)', async () => {
    const fetchSummary = vi.spyOn(forumService, 'fetchTopicSummary').mockResolvedValue(PENDING);
    const { unmount } = render(<ThreadSummaryPanel topicId={12} />);

    fireEvent.click(summarize());
    await advance(0);
    expect(fetchSummary).toHaveBeenCalledTimes(1);

    unmount();
    await advance(60_000);
    expect(fetchSummary).toHaveBeenCalledTimes(1);
  });

  it('does not start polling when a request that was in flight at unmount resolves pending', async () => {
    let resolveFirst: (value: TopicSummary) => void = () => {};
    const fetchSummary = vi
      .spyOn(forumService, 'fetchTopicSummary')
      .mockImplementationOnce(
        () =>
          new Promise<TopicSummary>((resolve) => {
            resolveFirst = resolve;
          })
      )
      .mockResolvedValue(PENDING);
    const { unmount } = render(<ThreadSummaryPanel topicId={12} />);

    fireEvent.click(summarize());
    unmount();
    await act(async () => {
      resolveFirst(PENDING);
    });
    await advance(60_000);

    expect(fetchSummary).toHaveBeenCalledTimes(1);
  });

  // --- PR #816 review round 1 ---

  it('on 401 (expired access cookie) says so, keeps the button, and never latches', async () => {
    vi.spyOn(forumService, 'fetchTopicSummary').mockRejectedValue(
      new forumService.TopicSummaryError(401, 'Authentication credentials were not provided.')
    );
    render(<ThreadSummaryPanel topicId={12} />);

    fireEvent.click(summarize());
    await advance(0);

    expect(statusRegion()).toHaveTextContent(/session expired/i);
    expect(summarize()).toBeEnabled();
    expect(forumService.isTopicSummaryUnavailable()).toBe(false);
  });

  it('aborts the in-flight request when unmounted', async () => {
    let seen: AbortSignal | undefined;
    vi.spyOn(forumService, 'fetchTopicSummary').mockImplementation((_id, signal) => {
      seen = signal;
      return new Promise<TopicSummary>(() => {});
    });
    const { unmount } = render(<ThreadSummaryPanel topicId={12} />);

    fireEvent.click(summarize());
    await advance(0);
    expect(seen?.aborted).toBe(false);

    unmount();
    expect(seen?.aborted).toBe(true);
  });

  it('renders the result inside a live region that exists before it arrives', async () => {
    vi.spyOn(forumService, 'fetchTopicSummary').mockResolvedValue(READY);
    render(<ThreadSummaryPanel topicId={12} />);
    const region = screen.getByTestId('thread-summary-result');
    expect(region).toHaveAttribute('aria-live', 'polite');
    expect(region).toBeEmptyDOMElement();

    fireEvent.click(summarize());
    await advance(0);

    expect(screen.getByTestId('thread-summary-result')).toBe(region);
    expect(region).toHaveTextContent(READY.summary);
  });
});
