import { useId, useRef } from 'react';
import Button from './Button';
import { useModalFocus } from '../../hooks/useModalFocus';

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
 * `aria-modal`); the confirm button is focused on open, Tab/Shift+Tab stay
 * inside the dialog, Escape and a backdrop click cancel, and focus is returned
 * to the trigger on close (`useModalFocus`).
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

  useModalFocus(open, dialogRef, onCancel);

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
        className="w-full max-w-sm rounded-lg bg-surface p-6 shadow-3"
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
