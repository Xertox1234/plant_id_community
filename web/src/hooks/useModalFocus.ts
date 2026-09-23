import { useEffect, useRef, type RefObject } from 'react';

// Disabled controls and tabindex="-1" are not in the Tab order, so they must
// not be the wrap targets either: the picker's last control is a "Load more"
// button that is disabled while a page loads.
const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), ' +
  'textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * Modal focus management for a `role="dialog"` + `aria-modal` panel (todo 396).
 *
 * While `open`:
 *   - the element marked `data-autofocus` inside `dialogRef` is focused;
 *   - Escape calls `onClose`;
 *   - Tab / Shift+Tab wrap inside the dialog instead of leaving it for the
 *     inert page behind it.
 * On close, focus returns to whatever was focused when the dialog opened.
 *
 * The trigger is captured ONCE per open. The effect that captures it depends
 * on `open` alone; `onClose` is read through a ref. Callers pass inline arrows
 * (`onClose={() => setOpen(false)}`), so an effect keyed on `onClose` re-ran on
 * every parent render. Each re-run re-captured `document.activeElement` -- by
 * then something INSIDE the dialog -- as the restore target, and yanked focus
 * back to the autofocused control.
 */
export function useModalFocus(
  open: boolean,
  dialogRef: RefObject<HTMLElement | null>,
  onClose: () => void
): void {
  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    if (!open) return;
    // Capture the trigger BEFORE moving focus in: a React `autoFocus` runs
    // during commit, i.e. before this effect, so document.activeElement would
    // already be inside the dialog.
    const previouslyFocused = document.activeElement as HTMLElement | null;
    dialogRef.current?.querySelector<HTMLElement>('[data-autofocus]')?.focus();

    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onCloseRef.current();
        return;
      }
      if (e.key !== 'Tab') return;
      const dialog = dialogRef.current;
      if (!dialog) return;
      const focusables = Array.from(dialog.querySelectorAll<HTMLElement>(FOCUSABLE));
      if (focusables.length === 0) {
        e.preventDefault();
        return;
      }
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      const active = document.activeElement;
      // Focus outside the dialog (e.g. the browser moved it to <body> after
      // the focused control was removed) is pulled back in as well.
      const inside = active instanceof Node && dialog.contains(active);
      if (e.shiftKey && (active === first || !inside)) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && (active === last || !inside)) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
      previouslyFocused?.focus?.();
    };
  }, [open, dialogRef]);
}
