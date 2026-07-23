import { useState, useEffect, useCallback, useMemo, FormEvent } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { createThread, fetchCategory } from '../../services/forumService';
import { parseLeadingId, threadPath, categoryPath } from '../../utils/forumUrls';
import { draftKey, loadDraft, saveDraft, clearDraft } from '../../utils/forumDrafts';
import TipTapEditor from '../../components/forum/TipTapEditor';
import LoadingSpinner from '../../components/ui/LoadingSpinner';
import Button from '../../components/ui/Button';
import PageMeta from '../../components/PageMeta';
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

  useEffect(() => {
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
        setCategory(await fetchCategory(forumId));
      } catch (err) {
        logger.error('Error loading board for new thread', {
          component: 'NewThreadPage',
          error: err,
          context: { categoryParam },
        });
        setError(err instanceof Error ? err.message : 'Failed to load board');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [categoryParam]);

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
          // A pending topic is live=False — opening it 404s. Confirm + return to board.
          window.alert('Your topic was submitted and is awaiting moderation.');
          navigate(categoryPath(category));
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
    [category, title, body, navigate, newThreadDraftKey]
  );

  if (loading) {
    return (
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <LoadingSpinner />
      </div>
    );
  }

  if (error && !category) {
    return (
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="bg-error/10 border border-error/30 text-ink px-4 py-3 rounded">
          <strong>Error:</strong> {error}
        </div>
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
