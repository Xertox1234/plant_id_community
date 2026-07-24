import { useEffect } from 'react';
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
 * `aria-modal`), the confirm button is auto-focused on open, Escape and a
 * backdrop click cancel, and focus is returned to the trigger on close.
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
  // Escape closes; restore focus to whatever was focused before opening.
  useEffect(() => {
    if (!open) return;
    const previouslyFocused = document.activeElement as HTMLElement | null;
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
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        aria-describedby="confirm-dialog-message"
        className="w-full max-w-sm rounded-lg bg-surface-1 p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="confirm-dialog-title" className="text-lg font-semibold text-ink mb-2">
          {title}
        </h2>
        <p id="confirm-dialog-message" className="text-ink-2 mb-4">
          {message}
        </p>
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onCancel} className="min-h-11">
            {cancelLabel}
          </Button>
          <Button autoFocus variant="primary" onClick={onConfirm} className="min-h-11">
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
