import { useCallback, useEffect, useRef } from 'react';
import { X } from 'lucide-react';
import Button from '../ui/Button';
import type { LiveToastSpec } from '../../types/forumLive';

/** How long a live-updates toast stays up when nobody is hovering or focusing it. */
export const LIVE_TOAST_MS = 10_000;

interface LiveToastProps {
  toast: LiveToastSpec | null;
  onDismiss: () => void;
}

/**
 * The topic page's one toast (forum live replies, slice 3): the first-time
 * "Replies now appear live." notice, its "Live updates off · Undo" follow-up,
 * and the signed-out "missing out" notice.
 *
 * The `role="status"` region is ALWAYS mounted and only its content swaps,
 * so a screen reader announces each toast (a live region created along with
 * its content says nothing, audit M26). The timer pauses while the toast is
 * hovered or holds focus, so a keyboard user can reach its action.
 */
export default function LiveToast({ toast, onDismiss }: LiveToastProps) {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onDismissRef = useRef(onDismiss);
  useEffect(() => {
    onDismissRef.current = onDismiss;
  }, [onDismiss]);

  const pause = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = null;
  }, []);
  const arm = useCallback(() => {
    pause();
    timerRef.current = setTimeout(() => onDismissRef.current(), LIVE_TOAST_MS);
  }, [pause]);

  const toastId = toast?.id ?? null;
  useEffect(() => {
    if (toastId == null) return;
    arm();
    return pause;
  }, [toastId, arm, pause]);

  return (
    <div
      role="status"
      aria-live="polite"
      aria-atomic="true"
      className={
        toast
          ? 'pointer-events-none fixed inset-x-0 bottom-20 z-20 flex justify-center px-4'
          : 'sr-only'
      }
    >
      {toast && (
        <div
          className="canopy-card pointer-events-auto flex max-w-md flex-wrap items-center gap-3 rounded-md px-4 py-3 shadow-2"
          onMouseEnter={pause}
          onMouseLeave={arm}
          onFocus={pause}
          onBlur={(event) => {
            if (!event.currentTarget.contains(event.relatedTarget as Node | null)) arm();
          }}
        >
          <p className="text-sm text-ink">{toast.message}</p>
          <div className="flex items-center gap-2">
            {toast.actions.map((action) => (
              <Button
                key={action.label}
                variant="outline"
                className="min-h-11"
                onClick={() => {
                  action.onClick();
                  onDismiss();
                }}
              >
                {action.label}
              </Button>
            ))}
            <button
              type="button"
              aria-label="Dismiss"
              onClick={onDismiss}
              className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-pill text-ink-3 hover:bg-primary/10"
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
