import { useState, useEffect, useCallback, useMemo, FormEvent } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { createThread, fetchCategory } from '../../services/forumService';
import { parseLeadingId, threadPath, categoryPath } from '../../utils/forumUrls';
import { draftKey, loadDraft, saveDraft, clearDraft } from '../../utils/forumDrafts';
import TipTapEditor from '../../components/forum/TipTapEditor';
import ForumErrorState from '../../components/forum/ForumErrorState';
import LoadingSpinner from '../../components/ui/LoadingSpinner';
import Button from '../../components/ui/Button';
import PageMeta from '../../components/PageMeta';
import { useAnnounce } from '../../contexts/AnnouncerContext';
import { logger } from '../../utils/logger';
import type { Category } from '@/types';

/** Strip tags + whitespace to detect an effectively-empty rich-text body. */
function isBlankHtml(html: string): boolean {
  return html.replace(/<[^>]*>/g, '').trim() === '';
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
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const categoryParam = searchParams.get('category');

  const [category, setCategory] = useState<Category | null>(null);
  const newThreadDraftKey = draftKey('new-thread', categoryParam ?? 'unknown');
  // Parse the saved draft once (per key), not once per field.
  const initialDraft = useMemo<{ title?: string; body?: string }>(() => {
    try {
      return JSON.parse(loadDraft(newThreadDraftKey) || '{}');
    } catch {
      return {};
    }
  }, [newThreadDraftKey]);
  const [title, setTitle] = useState<string>(() => initialDraft.title || '');
  const [body, setBody] = useState<string>(() => initialDraft.body || '');
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
      if (forumId == null) {
        setError('Invalid board. Open “New Thread” from a forum board.');
        setLoading(false);
        return;
      }
      try {
        setLoading(true);
        setError(null);
        const cat = await fetchCategory(forumId);
        if (!ignore) setCategory(cat);
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
    const isEmpty = title.trim() === '' && isBlankHtml(body);
    saveDraft(newThreadDraftKey, isEmpty ? '' : JSON.stringify({ title, body }));
  }, [title, body, newThreadDraftKey]);

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
    [category, title, body, navigate, newThreadDraftKey, announce]
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
