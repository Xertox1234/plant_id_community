import { useEffect, useId, useRef, useState } from 'react';
import StreamFieldRenderer from '../StreamFieldRenderer';
import Timestamp from '../ui/Timestamp';
import Button from '../ui/Button';
import LoadingSpinner from '../ui/LoadingSpinner';
import {
  ForumApiError,
  fetchPostRevision,
  fetchPostRevisions,
  type PostRevisionDetail,
  type PostRevisionSummary,
} from '../../services/forumService';

interface EditHistoryDialogProps {
  open: boolean;
  postId: string;
  onClose: () => void;
}

/**
 * EditHistoryDialog (todo 282 / audit M4)
 *
 * Every forum post edit has always been persisted as a Wagtail revision, and
 * PostCard has always stamped "Edited <time> by <user>" — with nothing behind
 * it. This is what the stamp opens: the list of revisions, and one revision's
 * body rendered through the same `StreamFieldRenderer` as the live post, so
 * the two are visually comparable without a second renderer.
 *
 * Modal semantics follow ConfirmDialog (audit M24 replaced the native dialogs):
 * `role="dialog"` + `aria-modal`, Escape and backdrop-click close, focus moved
 * in on open and returned to the trigger on close.
 *
 * A 403 is an expected state, not a failure. The backend serves history to the
 * post's author and to moderators, and turns it moderator-only once someone
 * else has edited the post — because the earlier revisions still contain
 * whatever that edit removed. Rendering that as "couldn't load" would be a lie;
 * it is rendered as the refusal it is.
 */
export default function EditHistoryDialog({ open, postId, onClose }: EditHistoryDialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const latestRequestRef = useRef<number | null>(null);
  const titleId = useId();
  const [revisions, setRevisions] = useState<PostRevisionSummary[] | null>(null);
  const [selected, setSelected] = useState<PostRevisionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    // Capture the trigger BEFORE moving focus in, mirroring ConfirmDialog: a
    // React `autoFocus` runs during commit, i.e. before this effect, so
    // document.activeElement would already be inside the dialog.
    const previouslyFocused = document.activeElement as HTMLElement | null;
    dialogRef.current?.querySelector<HTMLButtonElement>('[data-autofocus]')?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
      previouslyFocused?.focus?.();
    };
  }, [open, onClose]);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setIsLoading(true);
    setError(null);
    setSelected(null);
    latestRequestRef.current = null;
    fetchPostRevisions(postId)
      .then((data) => {
        if (!cancelled) setRevisions(data);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setRevisions(null);
        // Branch on the STATUS, never the message text: the backend serialises
        // DRF's PermissionDenied as "You do not have permission to perform this
        // action.", which contains neither "403" nor "forbidden" — a regex on
        // the message would silently route every real 403 to the generic
        // failure, defeating the whole point of distinguishing them.
        setError(
          e instanceof ForumApiError && e.status === 403
            ? 'This post has been edited by a moderator, so its history is only visible to moderators.'
            : "Couldn't load this post's edit history."
        );
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, postId]);

  if (!open) return null;

  const handleSelect = (revisionId: number) => {
    setError(null);
    // Same stale-response guard as the list fetch above: a response from a
    // previous open (or from a rapidly-superseded row click) must not
    // overwrite the current selection. useRef, not useState — this must not
    // re-render, and a state update would recreate the callback.
    latestRequestRef.current = revisionId;
    fetchPostRevision(postId, revisionId)
      .then((detail) => {
        if (latestRequestRef.current === revisionId) setSelected(detail);
      })
      .catch(() => {
        if (latestRequestRef.current === revisionId) {
          setError("Couldn't load that revision.");
        }
      });
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={onClose}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="flex max-h-[80vh] w-full max-w-2xl flex-col rounded-lg bg-surface p-6 shadow-3"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-start justify-between gap-4">
          <h2 id={titleId} className="gt-h3 text-ink">
            Edit history
          </h2>
          <Button data-autofocus variant="outline" onClick={onClose} className="min-h-11">
            Close
          </Button>
        </div>

        {/* Always-mounted live region: an ancestor that is conditionally
            rendered would recreate it with its content, which is the exact
            anti-pattern a live region exists to avoid. */}
        <p role="status" aria-live="polite" className="text-sm text-error">
          {error ?? ''}
        </p>

        <div className="min-h-0 flex-1 overflow-y-auto">
          {isLoading && <LoadingSpinner />}

          {!isLoading && revisions !== null && revisions.length === 0 && (
            <p className="text-sm text-ink-3">No revisions recorded for this post.</p>
          )}

          {!isLoading && revisions !== null && revisions.length > 0 && (
            <ul className="divide-y divide-line">
              {revisions.map((revision) => (
                <li key={revision.id}>
                  <button
                    type="button"
                    onClick={() => handleSelect(revision.id)}
                    aria-pressed={selected?.id === revision.id}
                    className="flex min-h-11 w-full items-center justify-between gap-2 px-1 py-2 text-left text-sm text-ink-2 hover:bg-surface-2"
                  >
                    <span>
                      <Timestamp iso={revision.created_at} />
                      {` — ${revision.user.display_name || revision.user.username}`}
                    </span>
                    <span className="text-xs text-primary">View</span>
                  </button>
                </li>
              ))}
            </ul>
          )}

          {selected && (
            <div className="mt-4 rounded-md border border-line p-4">
              <p className="mb-2 text-xs uppercase tracking-wide text-ink-3">
                Revision from <Timestamp iso={selected.created_at} />
              </p>
              <StreamFieldRenderer blocks={selected.body} mentionHighlight />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
