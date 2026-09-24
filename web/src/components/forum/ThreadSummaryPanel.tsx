import { useEffect, useRef, useState } from 'react';
import { Sparkles } from 'lucide-react';
import Button from '../ui/Button';
import {
  fetchTopicSummary,
  isTopicSummaryUnavailable,
  markTopicSummaryUnavailable,
  TopicSummaryError,
} from '../../services/forumService';
import { logger } from '../../utils/logger';
import type { TopicSummary } from '../../types/forum';

/**
 * ThreadSummaryPanel — the premium "Summarize thread" button (todo 414; backend
 * `GET /forum/topics/{id}/summary/`, apps/forum_host/summary.py).
 *
 * Premium is server-gated: the auth user payload carries no premium flag, so —
 * exactly like compose assist and plant-care ask — the server's 401/403 is what
 * tells us, latched in the service for the session. The panel that received it
 * shows the premium notice in place of the button; every later mount (the next
 * thread) renders nothing. `AuthContext` clears the latch on identity change.
 *
 * The endpoint never generates in-request: a cache miss returns 202 `pending`
 * and a Celery task writes the summary, so this polls. Sparingly — the 30/h
 * `topic_summary` bucket counts every poll — and boundedly: a generation that
 * never lands (global AI budget exhausted, provider down) ends in "try again",
 * not an endless loop that burns the user's hour.
 */

/** Delay between polls of a 202 `pending`. */
const POLL_DELAY_MS = 5000;
/** Polls after the first request (≈30s total; the pending lock's TTL is 120s). */
const MAX_POLLS = 6;
/** Mirrors SUMMARY_MIN_POSTS in apps/forum_host/constants.py. */
const MIN_POSTS = 3;

const STILL_WRITING = 'The summary is still being written. Try again in a minute.';
const SESSION_EXPIRED = 'Your session expired. Sign in again to summarize this thread.';
const GENERIC_ERROR = 'Couldn’t summarize this thread. Please try again.';

function throttledMessage(retryAfter: number | null): string {
  const when =
    retryAfter && retryAfter > 0 ? `in about ${Math.ceil(retryAfter / 60)} minutes` : 'later';
  return `You’ve reached the summary limit for now. Try again ${when}.`;
}

type Outcome = Exclude<TopicSummary, { status: 'pending' }>;

interface ThreadSummaryPanelProps {
  /** Canonical numeric topic id (the page's `topicId`, parsed from the URL). */
  topicId: number;
}

export default function ThreadSummaryPanel({ topicId }: ThreadSummaryPanelProps) {
  // Read once per mount: a latch set by an EARLIER panel means this account
  // can't use it — render nothing. One set during THIS mount keeps the notice.
  const [hiddenAtMount] = useState(isTopicSummaryUnavailable);
  const [unavailable, setUnavailable] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  // Poll timer + a run token: unmount bumps the token so an in-flight run
  // stops at its next await instead of polling for a thread no longer shown.
  // The abort cancels the request itself, which would otherwise still spend a
  // slot of the 30/h bucket for a thread nobody is viewing.
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const runRef = useRef(0);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(
    () => () => {
      runRef.current += 1;
      if (timerRef.current) clearTimeout(timerRef.current);
      abortRef.current?.abort();
    },
    []
  );

  if (hiddenAtMount) return null;

  const summarize = async () => {
    if (busy || unavailable) return;
    const run = ++runRef.current;
    const controller = new AbortController();
    abortRef.current = controller;
    setBusy(true);
    setMessage(null);
    setOutcome(null);
    try {
      for (let polls = 0; ; polls += 1) {
        const result = await fetchTopicSummary(topicId, controller.signal);
        if (runRef.current !== run) return;
        if (result.status !== 'pending') {
          setOutcome(result);
          break;
        }
        if (polls >= MAX_POLLS) {
          setMessage(STILL_WRITING);
          break;
        }
        await new Promise<void>((resolve) => {
          timerRef.current = setTimeout(resolve, POLL_DELAY_MS);
        });
        if (runRef.current !== run) return;
      }
    } catch (err) {
      if (runRef.current !== run) return;
      logger.error('Thread summary failed', {
        component: 'ThreadSummaryPanel',
        error: err instanceof Error ? err.message : String(err),
      });
      if (err instanceof TopicSummaryError && err.permanent) {
        // Not premium (403): retrying can never succeed for this account —
        // latch it so the next thread does not re-offer it.
        markTopicSummaryUnavailable();
        setUnavailable(true);
        setMessage(err.message);
      } else if (err instanceof TopicSummaryError && err.status === 401) {
        // An expired access cookie, not "can't": say so, never latch.
        setMessage(SESSION_EXPIRED);
      } else if (err instanceof TopicSummaryError && err.status === 429) {
        setMessage(throttledMessage(err.retryAfter));
      } else {
        setMessage(GENERIC_ERROR);
      }
    }
    setBusy(false);
  };

  return (
    <section className="canopy-card mb-6 p-4 sm:p-5" aria-labelledby="thread-summary-heading">
      <div className="flex flex-wrap items-center gap-3">
        <Sparkles className="h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
        <h2 id="thread-summary-heading" className="gt-h3 text-ink">
          Thread summary
        </h2>
        <span className="gt-label">AI · Premium</span>
        {!unavailable && (
          <Button
            size="sm"
            variant="secondary"
            className="ml-auto"
            loading={busy}
            loadingText="Summarizing…"
            disabled={busy}
            onClick={() => void summarize()}
          >
            Summarize thread
          </Button>
        )}
      </div>

      {/* Persistent live region — mounted for the panel's whole life. */}
      <p
        role="status"
        aria-live="polite"
        className={message ? 'mt-3 text-body-sm text-ink-2' : 'sr-only'}
      >
        {message ?? ''}
      </p>

      {/* Also a persistent live region: the result arrives after up to ~30s
          of polling, and content mounted into a region that already exists is
          what a screen reader announces (a freshly mounted node is not). */}
      <div aria-live="polite" data-testid="thread-summary-result">
        {outcome?.status === 'ready' && (
          <div className="mt-3">
            <p className="text-body leading-relaxed text-ink">{outcome.summary}</p>
            <p className="gt-label mt-2">
              AI summary of {outcome.post_count} posts — may miss nuance; read the thread for
              details.
            </p>
          </div>
        )}

        {outcome?.status === 'too_short' && (
          <p className="mt-3 text-body-sm text-ink-2">
            Threads need at least {MIN_POSTS} posts before they can be summarized.
          </p>
        )}
      </div>
    </section>
  );
}
