import { useState, useEffect, useCallback, useMemo, FormEvent } from 'react';
import { useNavigate, useSearchParams, useLocation, Link } from 'react-router-dom';
import { createThread, fetchCategories, fetchCategory } from '../../services/forumService';
import { parseLeadingId, threadPath, categoryPath } from '../../utils/forumUrls';
import { draftKey, loadDraft, saveDraft, clearDraft } from '../../utils/forumDrafts';
import { useIdentitySwap } from '../../hooks/useIdentitySwap';
import TipTapEditor from '../../components/forum/TipTapEditor';
import ForumErrorState from '../../components/forum/ForumErrorState';
import LoadingSpinner from '../../components/ui/LoadingSpinner';
import Button from '../../components/ui/Button';
import ButtonLink from '../../components/ui/ButtonLink';
import PageMeta from '../../components/PageMeta';
import { useAnnounce } from '../../contexts/AnnouncerContext';
import { useAuth } from '../../contexts/AuthContext';
import { useScrollToTop } from '../../hooks/useScrollToTop';
import { logger } from '../../utils/logger';
import type { Category, CreateIdentificationInput } from '@/types';

/**
 * Mirrors the backend's `WAGTAILFORUM_POLL_MAX_OPTIONS`/`_MIN_OPTIONS`
 * defaults. The server is the authority — it rejects a too-long or
 * too-short list with a 400 — so these only stop the composer offering a
 * row that would be refused on submit, and gate Post so a poll enabled but
 * left blank/underfilled can't reach the server at all (todo 309 review:
 * without this, ticking "Add a poll" and leaving it blank failed the WHOLE
 * thread submission with a raw validation-error dict, not just the poll).
 */
const MAX_POLL_OPTIONS = 10;
const MIN_POLL_OPTIONS = 2;

/** Strip tags + whitespace to detect an effectively-empty rich-text body. */
function isBlankHtml(html: string): boolean {
  return html.replace(/<[^>]*>/g, '').trim() === '';
}

/**
 * `now`, formatted for a `datetime-local` input's `min` attribute
 * (`YYYY-MM-DDTHH:mm`, LOCAL wall time — `datetime-local` has no timezone).
 * A soft nudge only: the server's own future-only check
 * (`validate_closes_at`) is what actually enforces this.
 */
function minPollCloseDateTime(): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  const now = new Date();
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}`;
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
 * Defense-in-depth (todo 297): the cookie-jar identity can switch mid-submit
 * (re-login as a different account in another tab) — the create request
 * already succeeded under whatever identity the cookie carried by then, so
 * this can't be prevented, only detected. Non-null means "don't silently
 * navigate/confirm as if the ORIGINAL user posted this" — show a notice
 * instead. `path` is null for a pending (not-yet-live) topic — there is
 * nothing to link to yet.
 */
interface IdentityDrift {
  path: string | null;
  asUsername: string | null;
  pending: boolean;
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
  // Optional close time. Empty means "never closes" (omitted from the
  // payload). `datetime-local`'s value has no timezone — it is LOCAL wall
  // time — so it must go through `new Date(...).toISOString()` before it
  // reaches the server, which stores and compares in UTC (todo 320 #7: a
  // plain `type="date"` input would submit local midnight, which can already
  // be in the past by the time it reaches validate_closes_at's future-only
  // check).
  const [pollClosesAt, setPollClosesAt] = useState<string>('');
  // How many options one voter may pick (todo 349). 1 is the classic
  // single-choice poll and is omitted from the payload; the server refuses a
  // value above the non-blank option count, so canSubmit folds that in too.
  const [pollMaxChoices, setPollMaxChoices] = useState<number>(1);
  const [loading, setLoading] = useState<boolean>(true);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  // A pending (untrusted-author) topic is live=False and 404s if opened, so we
  // show an on-page confirmation instead of navigating into it (M24 — replaces
  // window.alert, which was inaccessible and jarring).
  const [submittedPending, setSubmittedPending] = useState<boolean>(false);
  const [identityDrift, setIdentityDrift] = useState<IdentityDrift | null>(null);
  // Bumping this re-runs the board load — drives the initial fetch and the
  // error-state Retry; each run gets its own `ignore` cleanup flag.
  const [reloadKey, setReloadKey] = useState(0);
  const announce = useAnnounce();
  const { user, revalidateIdentity } = useAuth();
  // A passive account swap clears the stored drafts in AuthContext; this
  // page's own title/body/tags state would re-persist the previous account's
  // text on the next keystroke (code review, PR #629) — reset it and remount
  // the editor (TipTap takes its content at mount only).
  const [composerEpoch, setComposerEpoch] = useState<number>(0);
  useIdentitySwap(user?.id, () => {
    setTitle('');
    setBody('');
    setTagsInput('');
    setComposerEpoch((e) => e + 1);
  });

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

  // A poll left blank/underfilled is not a smaller poll — the server drops
  // blank rows and then rejects fewer than MIN_POLL_OPTIONS, so "enabled but
  // empty" is a guaranteed 400 that would otherwise take the whole topic
  // down with it. Vacuously valid when the toggle is off.
  const filledPollOptions = pollOptions.filter((option) => option.trim() !== '').length;
  // Clamped to the filled option count rather than validated against it: if
  // an option is blanked AFTER "3 of 3" was chosen, the select's option list
  // shrinks and a raw state of 3 would match nothing (an invisible selection
  // gating Post from another control). The clamp is the single value the
  // select shows, the payload sends, and the server accepts.
  const effectiveMaxChoices = Math.min(pollMaxChoices, Math.max(1, filledPollOptions));
  const pollValid =
    !pollEnabled || (pollQuestion.trim() !== '' && filledPollOptions >= MIN_POLL_OPTIONS);

  const canSubmit = !!category && title.trim() !== '' && !isBlankHtml(body) && pollValid;

  const handleSubmit = useCallback(
    async (e: FormEvent<HTMLFormElement>) => {
      e.preventDefault();
      if (!category || !title.trim() || isBlankHtml(body) || !pollValid) return;
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
          ...(pollEnabled
            ? {
                poll: {
                  question: pollQuestion,
                  options: pollOptions,
                  // Omitted (not sent as '') when blank — CreatePollInput
                  // treats absence as "never closes", and an empty string
                  // is not a valid ISO datetime for the server to parse.
                  ...(pollClosesAt ? { closes_at: new Date(pollClosesAt).toISOString() } : {}),
                  // Omitted for the single-choice default, so the classic
                  // payload is byte-for-byte what it was before todo 349.
                  ...(effectiveMaxChoices > 1 ? { max_choices: effectiveMaxChoices } : {}),
                },
              }
            : {}),
        });
        clearDraft(newThreadDraftKey);

        // Defense-in-depth (todo 297): the write already happened under
        // whatever identity the cookie carried — this can only detect a
        // switch, not prevent one. Compare the identity BEFORE the create
        // call against a fresh revalidation now; a TOCTOU race, but the
        // best available signal client-side. Checked regardless of
        // published/pending — a misattributed post silently landing in the
        // wrong user's moderation queue is the same failure either way.
        const actingUserId = user?.id ?? null;
        const current = await revalidateIdentity();
        const drifted = (current?.id ?? null) !== actingUserId;

        if (drifted) {
          setIdentityDrift({
            path:
              res.status === 'published'
                ? threadPath(category, { id: res.id, slug: res.slug, title: title.trim() })
                : null,
            asUsername: current?.username ?? null,
            pending: res.status !== 'published',
          });
        } else if (res.status === 'published') {
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
        const message = err instanceof Error ? err.message : 'Failed to create thread';
        setError(message);
        // The banner below is conditionally mounted, so it is never announced
        // on its own (audit 2026-09-04 M4; MDN live regions) — route the
        // failure through the persistent announcer like the success path.
        announce(message, 'assertive');
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
      effectiveMaxChoices,
      pollQuestion,
      pollOptions,
      pollClosesAt,
      pollValid,
      navigate,
      newThreadDraftKey,
      announce,
      user,
      revalidateIdentity,
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
        <div className="canopy-card rounded-md p-6 text-center space-y-3">
          <h1 className="gt-h3 text-ink">Thanks — your topic is awaiting moderation</h1>
          <p className="text-ink-2">
            A moderator will review it shortly, and it will appear on the board once approved.
          </p>
          <ButtonLink to={categoryPath(category)} variant="primary" className="min-h-11">
            Back to {category.name}
          </ButtonLink>
        </div>
      </div>
    );
  }

  if (identityDrift && category) {
    return (
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="canopy-card rounded-md p-6 text-center space-y-3">
          <h1 className="gt-h3 text-ink">Your session changed while posting</h1>
          <p className="text-ink-2">
            {identityDrift.asUsername
              ? `This topic was posted as ${identityDrift.asUsername}, not the account you started with.`
              : 'You were signed out while this topic was being posted.'}{' '}
            {identityDrift.pending
              ? 'It is awaiting moderation before it appears.'
              : "If this wasn't you, check your account."}
          </p>
          <ButtonLink
            to={identityDrift.path ?? categoryPath(category)}
            variant="primary"
            className="min-h-11"
          >
            {identityDrift.path ? 'View the topic' : `Back to ${category.name}`}
          </ButtonLink>
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
        title="Start a New Thread · Houseplant MD"
        description="Start a new discussion in the Houseplant MD community forum."
      />
      {/* Breadcrumb — collection path, in the mono data voice */}
      <nav className="gt-label mb-6" aria-label="Breadcrumb">
        <ol className="flex items-center gap-2">
          <li>
            <Link to="/forum" viewTransition className="hover:text-primary">
              Forum
            </Link>
          </li>
          <li aria-hidden="true">/</li>
          <li>
            <Link
              to={category ? categoryPath(category) : '/forum'}
              viewTransition
              className="hover:text-primary"
            >
              {category?.name}
            </Link>
          </li>
          <li aria-hidden="true">/</li>
          <li aria-current="page" className="text-ink-2">
            New Thread
          </li>
        </ol>
      </nav>

      <p className="gt-label mb-2">New entry{category && <> · {category.name}</>}</p>
      <h1 className="gt-h1 text-ink mb-6">Start a New Thread</h1>

      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Board picker — shown only when no board was pre-selected (L4). */}
        {boards.length > 0 && (
          <div>
            <label htmlFor="board-picker" className="gt-label block mb-1.5 transition-colors">
              Board
            </label>
            <select
              id="board-picker"
              value={category?.id ?? ''}
              onChange={(e) => setCategory(boards.find((b) => b.id === e.target.value) ?? null)}
              className="min-h-11 w-full rounded-sm border border-line bg-surface-2/60 px-4 py-2 text-ink focus:ring-2 focus:ring-secondary"
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
          <div className="canopy-card rounded-md p-4">
            <div className="flex items-start gap-4">
              {handoff?.identificationPreviewUrl && (
                <img
                  src={handoff.identificationPreviewUrl}
                  alt="Photo that will be attached to your question"
                  className="h-20 w-20 shrink-0 rounded-xs object-cover"
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
          <label htmlFor="thread-title" className="gt-label block mb-1.5 transition-colors">
            Title
          </label>
          {/* The title being typed renders in the display face, so what the
              user sees while typing matches how it will read once posted. */}
          <input
            id="thread-title"
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="A clear, specific title"
            maxLength={255}
            className="gt-h3 w-full rounded-sm border border-line bg-surface-2/60 px-4 py-2.5 text-xl text-ink placeholder:text-ink-3 focus:border-transparent focus:ring-2 focus:ring-secondary focus:outline-none"
          />
        </div>

        <div>
          <label htmlFor="thread-tags" className="gt-label block mb-1.5 transition-colors">
            Tags <span className="normal-case tracking-normal">(optional)</span>
          </label>
          <input
            id="thread-tags"
            type="text"
            value={tagsInput}
            onChange={(e) => setTagsInput(e.target.value)}
            placeholder="monstera, root rot, propagation"
            aria-describedby="thread-tags-hint"
            className="w-full px-4 py-2 font-mono text-sm border border-line rounded-sm focus:ring-2 focus:ring-secondary focus:border-transparent bg-surface-2/60 text-ink placeholder:text-ink-3"
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
            <div className="mt-3 space-y-3 rounded-md border border-line bg-surface-2 p-4">
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
                  className="w-full px-4 py-2 border border-line-2 rounded-sm focus:ring-2 focus:ring-primary focus:border-transparent bg-surface text-ink"
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
                      className="w-full px-4 py-2 border border-line-2 rounded-sm focus:ring-2 focus:ring-primary focus:border-transparent bg-surface text-ink"
                    />
                  ))}
                </div>
                {pollOptions.length < MAX_POLL_OPTIONS && (
                  <button
                    type="button"
                    onClick={() => setPollOptions((prev) => [...prev, ''])}
                    className="mt-2 min-h-11 rounded-xs px-3 text-sm font-medium text-primary hover:bg-surface-3"
                  >
                    + Add option
                  </button>
                )}
                <p className="mt-1 text-xs text-ink-3">
                  Two options minimum, {MAX_POLL_OPTIONS} maximum. Blank rows are ignored. Each
                  member votes once and cannot change it.
                </p>
              </fieldset>

              <div>
                <label
                  htmlFor="poll-max-choices"
                  className="block text-sm font-medium text-ink-2 mb-1"
                >
                  Choices per voter
                </label>
                {/* A select bounded by the filled option count, not a free
                    number input: it cannot offer a value the server would
                    refuse, and a controlled number input snaps to its
                    fallback on clear (typing "2" after a clear yields "12"). */}
                <select
                  id="poll-max-choices"
                  value={effectiveMaxChoices}
                  onChange={(e) => setPollMaxChoices(Number(e.target.value))}
                  className="w-24 px-4 py-2 border border-line-2 rounded-sm focus:ring-2 focus:ring-primary focus:border-transparent bg-surface text-ink"
                >
                  {Array.from({ length: Math.max(1, filledPollOptions) }, (_, i) => i + 1).map(
                    (n) => (
                      <option key={n} value={n}>
                        {n}
                      </option>
                    )
                  )}
                </select>
                <p className="mt-1 text-xs text-ink-3">
                  1 for a single-choice poll; up to the number of options for &ldquo;pick all that
                  apply&rdquo;.
                </p>
              </div>

              <div>
                <label
                  htmlFor="poll-closes-at"
                  className="block text-sm font-medium text-ink-2 mb-1"
                >
                  Closes <span className="font-normal text-ink-3">(optional)</span>
                </label>
                <input
                  id="poll-closes-at"
                  type="datetime-local"
                  value={pollClosesAt}
                  onChange={(e) => setPollClosesAt(e.target.value)}
                  min={minPollCloseDateTime()}
                  className="w-full px-4 py-2 border border-line-2 rounded-sm focus:ring-2 focus:ring-primary focus:border-transparent bg-surface text-ink"
                />
                <p className="mt-1 text-xs text-ink-3">Leave blank for a poll that never closes.</p>
              </div>
            </div>
          )}
        </div>

        <div>
          <span className="gt-label block mb-1.5 transition-colors">Message</span>
          <TipTapEditor
            key={composerEpoch}
            content={body}
            onChange={setBody}
            placeholder="Write your post..."
          />
        </div>

        {error && (
          <div className="bg-error/10 border border-error/30 text-ink px-4 py-3 rounded-md">
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
          <ButtonLink to={category ? categoryPath(category) : '/forum'} variant="outline">
            Cancel
          </ButtonLink>
        </div>
      </form>
    </div>
  );
}
