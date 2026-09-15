import { useCallback, useEffect, useId, useRef, useState } from 'react';
import Button from '../ui/Button';
import LoadingSpinner from '../ui/LoadingSpinner';
import { ForumApiError, listMyForumImages, type UploadedImage } from '../../services/forumService';

interface ForumImagePickerProps {
  open: boolean;
  onSelect: (image: UploadedImage) => void;
  onClose: () => void;
}

/**
 * ForumImagePicker (todo 374)
 *
 * "Choose from your photos" — the composer's alternative to uploading the same
 * file again. Backed by `GET /forum/images/mine/`, which is the caller's OWN
 * uploads, newest first.
 *
 * The scoping is the SERVER's (`uploaded_by_user=request.user`) and is not
 * re-applied here. Wagtail's `choose` permission is collection-wide; a personal
 * library rather than a shared browse of everyone's photos is this forum's
 * product decision, enforced in the one place that can enforce it.
 *
 * Three end states that must stay visually distinct, because collapsing any of
 * them into the spinner is the bug this component is most likely to have:
 *
 *   forbidden  403 — not a Forum Member. A real state the endpoint enforces.
 *   empty      a member who has never uploaded. Not an error; it names the
 *              upload button as the way out.
 *   failed     anything else.
 *
 * Modal semantics follow ConfirmDialog/EditHistoryDialog (audit M24):
 * `role="dialog"` + `aria-modal`, Escape and backdrop-click close, focus moved
 * in on open and returned to the trigger on close.
 */
export default function ForumImagePicker({ open, onSelect, onClose }: ForumImagePickerProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const [images, setImages] = useState<UploadedImage[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);

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
    setForbidden(false);
    setImages([]);
    setNextCursor(null);
    listMyForumImages()
      .then((page) => {
        if (cancelled) return;
        setImages(page.items);
        setNextCursor(page.meta.next ?? null);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        // Branch on the STATUS, never the message text. DRF serialises
        // PermissionDenied to a sentence containing neither "403" nor
        // "forbidden", so a regex on the message would route every real 403
        // into the generic failure and defeat the distinction entirely.
        if (e instanceof ForumApiError && e.status === 403) {
          setForbidden(true);
        } else {
          setError("Couldn't load your photos.");
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open]);

  const loadMore = useCallback(() => {
    if (!nextCursor || isLoadingMore) return;
    setIsLoadingMore(true);
    setError(null);
    listMyForumImages({ cursor: nextCursor })
      .then((page) => {
        // Append, never replace: the cursor walks forward and the already-
        // rendered tiles stay put, so the user does not lose their place.
        setImages((prev) => [...prev, ...page.items]);
        setNextCursor(page.meta.next ?? null);
      })
      .catch(() => {
        // The already-loaded page stays on screen — a failed "load more" must
        // not empty the grid the user is looking at.
        setError("Couldn't load more photos.");
      })
      .finally(() => setIsLoadingMore(false));
  }, [nextCursor, isLoadingMore]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={onClose}
      data-testid="forum-image-picker-backdrop"
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="max-h-[80vh] w-full max-w-2xl overflow-y-auto rounded-card bg-surface p-4 shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between gap-3">
          <h2 id={titleId} className="text-lg font-semibold text-ink">
            Your photos
          </h2>
          <Button variant="ghost" onClick={onClose} data-autofocus>
            Close
          </Button>
        </div>

        {isLoading ? (
          <div className="py-8 flex justify-center">
            <LoadingSpinner />
          </div>
        ) : forbidden ? (
          <p className="mt-4 text-sm text-ink-3" data-testid="forum-image-picker-forbidden">
            Your account isn&apos;t a forum member yet, so it has no photo library. Post in the
            forum once and this will fill up.
          </p>
        ) : error && images.length === 0 ? (
          <p className="mt-4 text-sm text-error">{error}</p>
        ) : images.length === 0 ? (
          <p className="mt-4 text-sm text-ink-3" data-testid="forum-image-picker-empty">
            You haven&apos;t shared any photos to the forum yet. Use the upload button to add your
            first one.
          </p>
        ) : (
          <>
            <ul className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
              {images.map((image) => (
                <li key={image.id}>
                  <button
                    type="button"
                    onClick={() => onSelect(image)}
                    className="group block w-full overflow-hidden rounded-card border border-line focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                  >
                    <img
                      src={image.url}
                      // The BUTTON carries the accessible name below; an alt
                      // here too would announce the photo twice.
                      alt=""
                      loading="lazy"
                      className="aspect-square w-full object-cover transition group-hover:opacity-90"
                    />
                    <span className="sr-only">
                      {image.alt ? `Insert photo: ${image.alt}` : 'Insert photo'}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
            {error && <p className="mt-3 text-sm text-error">{error}</p>}
            {nextCursor && (
              <div className="mt-4 flex justify-center">
                <Button variant="secondary" onClick={loadMore} disabled={isLoadingMore}>
                  {isLoadingMore ? 'Loading…' : 'Load more'}
                </Button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
