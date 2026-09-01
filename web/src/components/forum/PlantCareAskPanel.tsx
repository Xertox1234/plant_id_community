import { Fragment, useState } from 'react';
import { Link } from 'react-router-dom';
import { BookOpen, Flag, MessagesSquare, Sparkles } from 'lucide-react';
import Button from '../ui/Button';
import {
  askPlantCare,
  isPlantCareAskUnavailable,
  markPlantCareAskUnavailable,
  reportPlantCareAnswer,
  RagError,
} from '../../services/forumService';
import { threadPath } from '../../utils/forumUrls';
import { logger } from '../../utils/logger';
import type { PlantCareAnswer, PlantCareSource } from '../../types/forum';

/**
 * PlantCareAskPanel — the opt-in "ask about plant care" panel (todo 289 / M13).
 *
 * Returns a RAG answer TO THE ASKER, assembled only from this site's blog and
 * forum; never auto-posted into a thread (design doc §5). Provenance-forward
 * (guardrail 4): every `[n]` in the answer links to the cited passage, the
 * sources list carries kind + title + date so a 2019 thread and a fresh
 * article do not look equally authoritative, and the server's disclaimer is
 * always shown. "This is wrong" (guardrail 5) is one click away and confirms
 * only after the report request resolves (the PostCard rule).
 *
 * Availability follows the compose-assist contract: 401/403/`code:disabled`
 * are permanent for the session and latch in the service (a remount cannot
 * re-offer the action; `AuthContext` clears the latch on auth change);
 * `unavailable`/429/400 keep the form usable. The control stays MOUNTED when
 * disabled so the focus the user just placed on it is not dropped.
 */

const QUESTION_MAX = 500; // mirrors RAG_QUESTION_MAX_CHARS
const REPORT_DETAIL_MAX = 280; // mirrors RAG_REPORT_DETAIL_MAX_CHARS

const DISCLOSURE =
  'Answers are assembled only from this site’s blog and forum posts, always cite ' +
  'their sources, and are stored with your account so you can report a wrong one. ' +
  'Not expert advice.';
const NO_INFORMATION =
  'This site doesn’t have anything close enough to answer that yet. Try the forum ' +
  'search, or ask the community.';
const SIGN_IN = 'Sign in with a premium account to ask about plant care.';
const UNAVAILABLE_TITLE = 'Plant-care answers are not available for this account';

const CITATION_SPLIT = /(\[\d+(?:,\s*\d+)*\])/;
const CITATION_MATCH = /^\[(\d+(?:,\s*\d+)*)\]$/;

function sourceHref(source: PlantCareSource): string {
  if (source.kind === 'blog') {
    return `/blog/${source.slug}${source.anchor ? `#${source.anchor}` : ''}`;
  }
  // The client composes the route (no server URL building — todo 308).
  return threadPath(
    { id: String(source.board_id), slug: source.board_slug, name: source.board_slug },
    { id: String(source.topic_id), slug: source.topic_slug, title: source.title }
  );
}

function formatSourceDate(value: string): string {
  // A date-only string parsed bare is UTC midnight and renders the previous
  // day in negative-offset timezones — anchor it to local midnight.
  const date = value.length === 10 ? new Date(`${value}T00:00:00`) : new Date(value);
  return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
}

function AnswerText({ answer, sources }: { answer: string; sources: PlantCareSource[] }) {
  const byNumber = new Map(sources.map((s) => [s.n, s]));
  return (
    <p className="text-[15px] leading-relaxed text-ink">
      {answer.split(CITATION_SPLIT).map((part, i) => {
        const match = part.match(CITATION_MATCH);
        if (!match) return <Fragment key={i}>{part}</Fragment>;
        const numbers = match[1].split(',').map((n) => parseInt(n.trim(), 10));
        return (
          <span key={i} className="font-mono text-[12px] text-ink-2">
            [
            {numbers.map((n, j) => {
              const source = byNumber.get(n);
              return (
                <Fragment key={n}>
                  {j > 0 && ', '}
                  {source ? (
                    <Link
                      to={sourceHref(source)}
                      aria-label={`Source ${n}: ${source.title}`}
                      className="text-primary underline-offset-2 hover:underline"
                    >
                      {n}
                    </Link>
                  ) : (
                    n
                  )}
                </Fragment>
              );
            })}
            ]
          </span>
        );
      })}
    </p>
  );
}

function SourceList({ sources }: { sources: PlantCareSource[] }) {
  return (
    <ol aria-label="Sources" className="mt-3 space-y-2">
      {sources.map((source) => (
        <li key={source.n} className="flex flex-col gap-0.5 text-[13px]">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-[11px] text-ink-3">[{source.n}]</span>
            <span className="inline-flex items-center gap-1 rounded-pill border border-line px-2 py-0.5 text-[11px] text-ink-2">
              {source.kind === 'blog' ? (
                <BookOpen className="h-3 w-3" aria-hidden="true" />
              ) : (
                <MessagesSquare className="h-3 w-3" aria-hidden="true" />
              )}
              {source.kind === 'blog' ? 'Blog article' : 'Forum thread'}
            </span>
            <Link to={sourceHref(source)} className="font-medium text-ink hover:underline">
              {source.title}
            </Link>
            <time dateTime={source.date} className="text-ink-3">
              {formatSourceDate(source.date)}
            </time>
          </div>
          {source.snippet && <p className="text-ink-2">{source.snippet}</p>}
        </li>
      ))}
    </ol>
  );
}

interface PlantCareAskPanelProps {
  /** Seeds the question box when the panel is opened (never auto-submits). */
  initialQuestion?: string;
}

export default function PlantCareAskPanel({ initialQuestion = '' }: PlantCareAskPanelProps) {
  const [open, setOpen] = useState(false);
  const [question, setQuestion] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [unavailable, setUnavailable] = useState(isPlantCareAskUnavailable);
  const [result, setResult] = useState<PlantCareAnswer | null>(null);
  const [reporting, setReporting] = useState(false);
  const [reportDetail, setReportDetail] = useState('');
  const [reportBusy, setReportBusy] = useState(false);
  const [reported, setReported] = useState(false);
  const [reportError, setReportError] = useState<string | null>(null);

  const toggle = () => {
    if (!open && !question) setQuestion(initialQuestion);
    setOpen((o) => !o);
  };

  const ask = async () => {
    const trimmed = question.trim();
    if (!trimmed || busy || unavailable) return;
    setBusy(true);
    setError(null);
    setResult(null);
    setReporting(false);
    setReported(false);
    setReportError(null);
    try {
      setResult(await askPlantCare(trimmed));
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Something went wrong.';
      logger.error('Plant-care ask failed', { component: 'PlantCareAskPanel', error: message });
      if (err instanceof RagError && err.permanent) {
        // Retrying can never succeed for this visitor/deployment — remember it
        // in the service so a remounted panel does not re-offer the action.
        markPlantCareAskUnavailable();
        setUnavailable(true);
        setError(err.status === 401 ? SIGN_IN : message);
      } else {
        setError(message);
      }
    } finally {
      setBusy(false);
    }
  };

  const submitReport = async () => {
    if (!result || result.status !== 'answered' || reportBusy) return;
    setReportBusy(true);
    setReportError(null);
    try {
      await reportPlantCareAnswer(result.answer_id, reportDetail.trim());
      // Only confirm once the request actually succeeded (PostCard rule).
      setReported(true);
      setReporting(false);
    } catch (err) {
      logger.error('Plant-care report failed', {
        component: 'PlantCareAskPanel',
        error: err instanceof Error ? err.message : String(err),
      });
      setReportError('Could not send your report. Please try again.');
    } finally {
      setReportBusy(false);
    }
  };

  return (
    <section className="canopy-card mb-6 p-4 sm:p-5" aria-labelledby="plant-care-ask-heading">
      <button
        type="button"
        onClick={toggle}
        aria-expanded={open}
        aria-controls="plant-care-ask-body"
        className="flex w-full items-center gap-3 text-left"
      >
        <Sparkles className="h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
        <span id="plant-care-ask-heading" className="gt-h3 text-ink">
          Ask about plant care
        </span>
        <span className="gt-label">AI · Premium</span>
      </button>
      <p className="mt-2 text-[13px] text-ink-2">{DISCLOSURE}</p>

      {open && (
        <div id="plant-care-ask-body" className="mt-4">
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void ask();
            }}
            className="flex flex-col gap-2"
          >
            <label htmlFor="plant-care-question" className="gt-label">
              Your question
            </label>
            <textarea
              id="plant-care-question"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              maxLength={QUESTION_MAX}
              rows={2}
              disabled={unavailable}
              placeholder="e.g. how often should I water a pothos in winter?"
              className="w-full rounded-md border border-line bg-surface-2/60 px-3 py-2 text-ink placeholder:text-ink-3 focus:border-transparent focus:ring-2 focus:ring-secondary focus:outline-none disabled:opacity-60"
            />
            <div className="flex items-center justify-between gap-3">
              <span className="font-mono text-[11px] text-ink-3">{`${question.length}/${QUESTION_MAX}`}</span>
              <Button
                type="submit"
                size="sm"
                loading={busy}
                loadingText="Asking…"
                disabled={unavailable || busy || !question.trim()}
                title={unavailable ? UNAVAILABLE_TITLE : undefined}
              >
                Ask
              </Button>
            </div>
          </form>

          {/* Persistent live region — always mounted while the body is open. */}
          <p
            role="status"
            aria-live="polite"
            className={error ? 'mt-3 text-[13px] text-error' : 'sr-only'}
          >
            {error ?? ''}
          </p>

          {result?.status === 'referral' && (
            <p className="mt-4 text-[14px] leading-relaxed text-ink">{result.referral.message}</p>
          )}

          {result?.status === 'no_information' && (
            <p className="mt-4 text-[14px] leading-relaxed text-ink-2">{NO_INFORMATION}</p>
          )}

          {result?.status === 'passages_only' && (
            <div className="mt-4">
              <p className="text-[14px] text-ink-2">
                No confident answer — here’s what the site has:
              </p>
              <SourceList sources={result.sources} />
              <p className="gt-label mt-3">{result.disclaimer}</p>
            </div>
          )}

          {result?.status === 'answered' && (
            <div className="mt-4">
              <AnswerText answer={result.answer} sources={result.sources} />
              <p className="gt-label mt-3">{result.disclaimer}</p>
              <SourceList sources={result.sources} />

              <div className="mt-4 border-t border-line pt-3">
                {reported ? (
                  <p className="text-[13px] text-ink-2">
                    Reported — thanks, a moderator will review it.
                  </p>
                ) : reporting ? (
                  <form
                    onSubmit={(event) => {
                      event.preventDefault();
                      void submitReport();
                    }}
                    className="flex flex-col gap-2"
                  >
                    <label htmlFor="plant-care-report-detail" className="gt-label">
                      What is wrong? (optional)
                    </label>
                    <textarea
                      id="plant-care-report-detail"
                      value={reportDetail}
                      onChange={(event) => setReportDetail(event.target.value)}
                      maxLength={REPORT_DETAIL_MAX}
                      rows={2}
                      className="w-full rounded-md border border-line bg-surface-2/60 px-3 py-2 text-[13px] text-ink focus:border-transparent focus:ring-2 focus:ring-secondary focus:outline-none"
                    />
                    {reportError && <p className="text-[13px] text-error">{reportError}</p>}
                    <div className="flex items-center gap-2">
                      <Button type="submit" size="sm" variant="secondary" loading={reportBusy}>
                        Submit report
                      </Button>
                      <button
                        type="button"
                        onClick={() => setReporting(false)}
                        disabled={reportBusy}
                        className="min-h-11 rounded-pill px-3 py-1 text-sm text-ink-3 hover:bg-surface-2 disabled:opacity-50"
                      >
                        Cancel
                      </button>
                    </div>
                  </form>
                ) : (
                  <button
                    type="button"
                    onClick={() => setReporting(true)}
                    className="inline-flex min-h-11 items-center gap-1.5 rounded-pill px-3 py-1 text-sm text-ink-3 hover:bg-error/10 hover:text-error"
                  >
                    <Flag className="h-3.5 w-3.5" aria-hidden="true" /> This is wrong
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
