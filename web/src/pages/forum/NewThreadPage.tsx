import { useState, useEffect, useCallback, useMemo, FormEvent } from 'react';
import { useNavigate, useSearchParams, useLocation, Link } from 'react-router-dom';
import { createThread, fetchCategories, fetchCategory } from '../../services/forumService';
import { parseLeadingId, threadPath, categoryPath } from '../../utils/forumUrls';
import { draftKey, loadDraft, saveDraft, clearDraft } from '../../utils/forumDrafts';
import TipTapEditor from '../../components/forum/TipTapEditor';
import ForumErrorState from '../../components/forum/ForumErrorState';
import LoadingSpinner from '../../components/ui/LoadingSpinner';
import Button from '../../components/ui/Button';
import PageMeta from '../../components/PageMeta';
import { useAnnounce } from '../../contexts/AnnouncerContext';
import { useScrollToTop } from '../../hooks/useScrollToTop';
import { logger } from '../../utils/logger';
import type { Category, CreateIdentificationInput } from '@/types';

/**
 * Mirrors the backend's `WAGTAILFORUM_POLL_MAX_OPTIONS` default. The server is
 * the authority — it rejects an over-long list with a 400 — so this only stops
 * the composer offering a row that would be refused on submit.
 */
const MAX_POLL_OPTIONS = 10;

/** Strip tags + whitespace to detect an effectively-empty rich-text body. */
function isBlankHtml(html: string): boolean {
  return html.replace(/<[^>]*>/g, '').trim() === '';
}

/**
 * The handoff the identify page pushes through router state (audit M6). The
 * photo is ALREADY uploaded by then — only JSON travels — so a failed upload
 * surfaces on the page where the user pressed the button, and this state stays
 * serializable.
 */
interface IdentificationHandoff {
  identification: CreateIdentificationInput;
  /** Absolute URL of the uploaded photo, for the composer's preview only. */
  identificationPreviewUrl?: string;
}

/**
 * Read the handoff defensively. Router state is `null` after a reload or a
 * direct visit, and nothing stops a hand-crafted history entry — so validate
 * rather than cast. A malformed handoff degrades to "no attachment", never a
 * crash mid-compose.
 */
function readHandoff(state: unknown): IdentificationHandoff | null {
  if (!state || typeof state !== 'object') return null;
  const candidateState = state as Partial<IdentificationHandoff>;
  const candidates = candidateState.identification?.candidates;
  if (!Array.isArray(candidates) || candidates.length === 0) return null;
  return {
    identification: candidateState.identification as CreateIdentificationInput,
    identificationPreviewUrl: candidateState.identificationPreviewUrl,
  };
}

/**
 * NewThreadPage Component
 *
 * Compose a new topic on a board. Reached via `/forum/new-thread?category={id}-{slug}`.
 * On success: a published topic navigates into the new thread; a pending topic
 * (untrusted author) is live=False and would 404 if opened, so we surface a
 * moderation notice and return to the board instead.
 */
export default function NewThreadPage() {
  useScrollToTop();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const location = useLocation();
  const categoryParam = searchParams.get('category');

  // The "Ask the community" handoff (audit M6). Deliberately NOT persisted into
  // the sessionStorage draft: the draft outlives the uploaded image's relevance,
  // and a stale image_id would fail the server's ownership check at submit. A
  // reload therefore degrades to a plain composer — the text is kept, the
  // attachment is not.
  const handoff = useMemo(() => readHandoff(location.state), [location.state]);
  const [identification, setIdentification] = useState<CreateIdentificationInput | null>(
    () => handoff?.identification ?? null
  );

  const [category, setCategory] = useState<Category | null>(null);
  // Boards for the composer picker when no `?category=` was supplied (L4) — lets
  // a user start a thread without first navigating into a specific board.
  const [boards, setBoards] = useState<Category[]>([]);
  const newThreadDraftKey = draftKey('new-thread', categoryParam ?? 'unknown');
  // Parse the saved draft once (per key), not once per field.
  const initialDraft = useMemo<{ title?: string; body?: string; tags?: string }>(() => {
    try {
      return JSON.parse(loadDraft(newThreadDraftKey) || '{}');
    } catch {
      return {};
    }
  }, [newThreadDraftKey]);
  // A saved draft always wins over the handoff's suggestion — the user's own
  // half-written title must never be overwritten by a machine guess.
  const [title, setTitle] = useState<string>(
    () =>
      initialDraft.title || (handoff ? `Is this ${handoff.identification.candidates[0].name}?` : '')
  );
  const [body, setBody] = useState<string>(() => initialDraft.body || '');
  // Comma-separated raw input (audit M5). Kept as the user's literal string in
  // state (and in the draft) so a half-typed tag isn't destroyed mid-keystroke;
  // it is split/trimmed only at submit. The server normalizes and bounds it.
  const [tagsInput, setTagsInput] = useState<string>(() => initialDraft.tags || '');
  // Optional poll (audit M8). Deliberately NOT part of the autosaved draft:
  // the draft is a plain string blob keyed on title/body/tags, and widening it
  // would invalidate every draft already in a member's browser.
  const [pollEnabled, setPollEnabled] = useState<boolean>(false);
  const [pollQuestion, setPollQuestion] = useState<string>('');
  // Starts at the minimum viable poll — two empty rows to fill in.
  const [pollOptions, setPollOptions] = useState<string[]>(['', '']);
  const [loading, setLoading] = useState<boolean>(true);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  // A pending (untrusted-author) topic is live=False and 404s if opened, so we
  // show an on-page confirmation instead of navigating into it (M24 — replaces
  // window.alert, which was inaccessible and jarring).
  const [submittedPending, setSubmittedPending] = useState<boolean>(false);
  // Bumping this re-runs the board load — drives the initial fetch and the
  // error-state Retry; each run gets its own `ignore` cleanup flag.
  const [reloadKey, setReloadKey] = useState(0);
  const announce = useAnnounce();

  useEffect(() => {
    // react.dev race guard: drop a stale response (unmount, or a retry/param
    // change superseding an in-flight request) instead of setting state.
    let ignore = false;
    const load = async () => {
      const forumId = parseLeadingId(categoryParam ?? undefined);
      try {
        setLoading(true);
        setError(null);
        if (forumId == null) {
          // No board pre-selected — load the list and let the user pick (L4)
          // instead of dead-ending on an "invalid board" error.
          const list = await fetchCategories();
          if (!ignore) setBoards(list);
        } else {
          const cat = await fetchCategory(forumId);
          if (!ignore) setCategory(cat);
        }
      } catch (err) {
        if (ignore) return;
        logger.error('Error loading board for new thread', {
          component: 'NewThreadPage',
          error: err,
          context: { categoryParam },
        });
        setError(err instanceof Error ? err.message : 'Failed to load board');
      } finally {
        if (!ignore) setLoading(false);
      }
    };
    load();
    return () => {
      ignore = true;
    };
  }, [categoryParam, reloadKey]);

  // Persist the draft on every change; an all-empty draft is removed.
  useEffect(() => {
    const isEmpty = title.trim() === '' && isBlankHtml(body) && tagsInput.trim() === '';
    saveDraft(newThreadDraftKey, isEmpty ? '' : JSON.stringify({ title, body, tags: tagsInput }));
  }, [title, body, tagsInput, newThreadDraftKey]);

  const canSubmit = !!category && title.trim() !== '' && !isBlankHtml(body);

  const handleSubmit = useCallback(
    async (e: FormEvent<HTMLFormElement>) => {
      e.preventDefault();
      if (!category || !title.trim() || isBlankHtml(body)) return;
      try {
        setSubmitting(true);
        setError(null);
        const res = await createThread({
          boardSlug: category.slug,
          title: title.trim(),
          content: body,
          tags: tagsInput
            .split(',')
            .map((t) => t.trim())
            .filter(Boolean),
          // Omitted entirely on the common no-attachment compose, so the
          // ordinary payload is unchanged by this feature.
          ...(identification ? { identification } : {}),
          // Same rule for the poll. Blank rows are sent as-is rather than
          // filtered here — the server drops them and owns the min/max/unique
          // rules, so the composer has exactly one authority to agree with
          // instead of a second copy that can drift out of step.
          ...(pollEnabled ? { poll: { question: pollQuestion, options: pollOptions } } : {}),
        });
        clearDraft(newThreadDraftKey);
        if (res.status === 'published') {
          navigate(threadPath(category, { id: res.id, slug: res.slug, title: title.trim() }));
        } else {
          // Pending → show the on-page confirmation and announce it (M24).
          setSubmittedPending(true);
          announce('Your topic was submitted and is awaiting moderation.', 'polite');
        }
      } catch (err) {
        logger.error('Error creating thread', {
          component: 'NewThreadPage',
          error: err,
          context: { board: category.slug },
        });
        setError(err instanceof Error ? err.message : 'Failed to create thread');
      } finally {
        setSubmitting(false);
      }
    },
    [
      category,
      title,
      body,
      tagsInput,
      identification,
      pollEnabled,
      pollQuestion,
      pollOptions,
      navigate,
      newThreadDraftKey,
      announce,
    ]
  );

  if (loading) {
    return (
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <LoadingSpinner />
      </div>
    );
  }

  if (submittedPending && category) {
    return (
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="rounded-lg border border-line bg-surface-2 p-6 text-center space-y-3">
          <h1 className="text-xl font-semibold text-ink">
            Thanks — your topic is awaiting moderation
          </h1>
          <p className="text-ink-2">
            A moderator will review it shortly, and it will appear on the board once approved.
          </p>
          <Link to={categoryPath(category)} className="inline-block">
            <Button variant="primary" className="min-h-11">
              Back to {category.name}
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  if (error && !category) {
    return (
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <ForumErrorState message={error} onRetry={() => setReloadKey((k) => k + 1)} />
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <PageMeta
        title="Start a New Thread · PlantID"
        description="Start a new discussion in the Plant Community forums."
      />
      {/* Breadcrumb */}
      <nav className="mb-6 text-sm text-ink-2" aria-label="Breadcrumb">
        <ol className="flex items-center gap-2">
          <li>
            <Link to="/forum" className="hover:text-primary">
              Forums
            </Link>
          </li>
          <li aria-hidden="true">›</li>
          <li>
            <Link to={category ? categoryPath(category) : '/forum'} className="hover:text-primary">
              {category?.name}
            </Link>
          </li>
          <li aria-hidden="true">›</li>
          <li aria-current="page" className="font-medium text-ink">
            New Thread
          </li>
        </ol>
      </nav>

      <h1 className="text-3xl font-bold text-ink mb-6">Start a New Thread</h1>

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Board picker — shown only when no board was pre-selected (L4). */}
        {boards.length > 0 && (
          <div>
            <label htmlFor="board-picker" className="block text-sm font-medium text-ink-2 mb-1">
              Board
            </label>
            <select
              id="board-picker"
              value={category?.id ?? ''}
              onChange={(e) => setCategory(boards.find((b) => b.id === e.target.value) ?? null)}
              className="min-h-11 w-full px-4 py-2 border border-line-2 rounded-lg focus:ring-2 focus:ring-primary bg-surface-2 text-ink"
            >
              <option value="" disabled>
                Choose a board…
              </option>
              {boards.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Attached identification (audit M6). Shown BEFORE the title so the
            user can see — and drop — what they are about to publish alongside
            their question; it carries their photo, so silently attaching it
            would be the wrong default. */}
        {identification && (
          <div className="rounded-lg border border-line bg-surface-3 p-4">
            <div className="flex items-start gap-4">
              {handoff?.identificationPreviewUrl && (
                <img
                  src={handoff.identificationPreviewUrl}
                  alt="Photo that will be attached to your question"
                  className="h-20 w-20 shrink-0 rounded object-cover"
                />
              )}
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-ink">Identification attached</p>
                <p className="mt-1 text-sm text-ink-2">
                  {identification.candidates
                    .map((c) => `${c.name} (${Math.round(c.confidence * 100)}%)`)
                    .join(', ')}
                </p>
              </div>
              <Button
                type="button"
                variant="outline"
                onClick={() => setIdentification(null)}
                className="shrink-0"
              >
                Remove
              </Button>
            </div>
          </div>
        )}

        <div>
          <label htmlFor="thread-title" className="block text-sm font-medium text-ink-2 mb-1">
            Title
          </label>
          <input
            id="thread-title"
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="A clear, specific title"
            maxLength={255}
            className="w-full px-4 py-2 border border-line-2 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent bg-surface-2 text-ink"
          />
        </div>

        <div>
          <label htmlFor="thread-tags" className="block text-sm font-medium text-ink-2 mb-1">
            Tags <span className="font-normal text-ink-3">(optional)</span>
          </label>
          <input
            id="thread-tags"
            type="text"
            value={tagsInput}
            onChange={(e) => setTagsInput(e.target.value)}
            placeholder="monstera, root rot, propagation"
            aria-describedby="thread-tags-hint"
            className="w-full px-4 py-2 border border-line-2 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent bg-surface-2 text-ink"
          />
          <p id="thread-tags-hint" className="mt-1 text-xs text-ink-3">
            Comma-separated. Up to 5 tags, e.g. species, genus, or symptom.
          </p>
        </div>

        {/* Optional poll (audit M8). Collapsed behind a toggle so the ordinary
            compose is visually unchanged — most threads carry no poll. Polls
            can only be attached HERE: they are not editable afterwards, since
            changing a question once votes exist rewrites what they meant. */}
        <div>
          <label className="flex items-center gap-2 text-sm font-medium text-ink-2">
            <input
              type="checkbox"
              checked={pollEnabled}
              onChange={(e) => setPollEnabled(e.target.checked)}
              className="h-4 w-4"
            />
            Add a poll <span className="font-normal text-ink-3">(optional)</span>
          </label>

          {pollEnabled && (
            <div className="mt-3 space-y-3 rounded-lg border border-line bg-surface-2 p-4">
              <div>
                <label
                  htmlFor="poll-question"
                  className="block text-sm font-medium text-ink-2 mb-1"
                >
                  Poll question
                </label>
                <input
                  id="poll-question"
                  type="text"
                  value={pollQuestion}
                  onChange={(e) => setPollQuestion(e.target.value)}
                  maxLength={300}
                  placeholder="Best soil mix for aroids?"
                  className="w-full px-4 py-2 border border-line-2 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent bg-surface text-ink"
                />
              </div>

              <fieldset>
                <legend className="block text-sm font-medium text-ink-2 mb-1">Options</legend>
                <div className="space-y-2">
                  {pollOptions.map((option, index) => (
                    <input
                      // Index keys are correct here and only here: these inputs
                      // are a fixed positional list with no reordering or
                      // removal, so an index IS each row's stable identity.
                      key={index}
                      type="text"
                      value={option}
                      onChange={(e) =>
                        setPollOptions((prev) =>
                          prev.map((value, i) => (i === index ? e.target.value : value))
                        )
                      }
                      maxLength={200}
                      aria-label={`Poll option ${index + 1}`}
                      placeholder={`Option ${index + 1}`}
                      className="w-full px-4 py-2 border border-line-2 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent bg-surface text-ink"
                    />
                  ))}
                </div>
                {pollOptions.length < MAX_POLL_OPTIONS && (
                  <button
                    type="button"
                    onClick={() => setPollOptions((prev) => [...prev, ''])}
                    className="mt-2 min-h-11 rounded px-3 text-sm font-medium text-primary hover:bg-surface-3"
                  >
                    + Add option
                  </button>
                )}
                <p className="mt-1 text-xs text-ink-3">
                  Two options minimum, {MAX_POLL_OPTIONS} maximum. Blank rows are ignored. Members
                  get one vote each and cannot change it.
                </p>
              </fieldset>
            </div>
          )}
        </div>

        <div>
          <span className="block text-sm font-medium text-ink-2 mb-1">Message</span>
          <TipTapEditor content={body} onChange={setBody} placeholder="Write your post..." />
        </div>

        {error && (
          <div className="bg-error/10 border border-error/30 text-ink px-4 py-3 rounded">
            {error}
          </div>
        )}

        <div className="flex gap-2">
          <Button
            type="submit"
            variant="primary"
            disabled={!canSubmit || submitting}
            loading={submitting}
            loadingText="Posting…"
          >
            Post Thread
          </Button>
          <Link to={category ? categoryPath(category) : '/forum'}>
            <Button type="button" variant="outline">
              Cancel
            </Button>
          </Link>
        </div>
      </form>
    </div>
  );
}
