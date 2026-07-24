import { useEffect, useId, useRef } from 'react';
import Button from './Button';

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
}

/**
 * ConfirmDialog
 *
 * A styled, accessible replacement for the native `window.confirm()` used in
 * forum flows (audit 2026-07-11 M24). Modal semantics (`role="dialog"`,
 * `aria-modal`); the confirm button is focused on open, Escape and a backdrop
 * click cancel, and focus is returned to the trigger on close.
 */
export default function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  // Unique per instance so two dialogs on one page (delete + edit-switch) don't
  // share aria-labelledby/-describedby ids.
  const titleId = useId();
  const messageId = useId();

  useEffect(() => {
    if (!open) return;
    // Capture the trigger BEFORE moving focus into the dialog, then focus the
    // confirm button. A React `autoFocus` prop runs during the commit phase —
    // before this effect — so `document.activeElement` would already be the
    // button and the real trigger (to restore on close) would be lost.
    const previouslyFocused = document.activeElement as HTMLElement | null;
    dialogRef.current?.querySelector<HTMLButtonElement>('[data-autofocus]')?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCancel();
    };
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
      previouslyFocused?.focus?.();
    };
  }, [open, onCancel]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={onCancel}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={messageId}
        className="w-full max-w-sm rounded-lg bg-surface-1 p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id={titleId} className="text-lg font-semibold text-ink mb-2">
          {title}
        </h2>
        <p id={messageId} className="text-ink-2 mb-4">
          {message}
        </p>
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onCancel} className="min-h-11">
            {cancelLabel}
          </Button>
          <Button data-autofocus variant="primary" onClick={onConfirm} className="min-h-11">
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
