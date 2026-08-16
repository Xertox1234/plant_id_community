import { useEffect } from 'react';

// Module-level, shared by every consumer (mobile drawer, command palette,
// any future modal) — locking/restoring `document.body.style.overflow`
// directly from each component's own effect composes incorrectly: with two
// lockers open at once, whichever effect's cleanup runs LAST clobbers the
// other's lock, and closing either one can unlock the page while the other
// is still open (code review finding #5, PR #538). A single module-level
// counter makes "locked" a property of the page, not of any one component:
// the body locks on the FIRST acquire and only restores on the LAST release.
let lockCount = 0;
let previousOverflow = '';

function acquire(): void {
  if (lockCount === 0) {
    previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
  }
  lockCount += 1;
}

function release(): void {
  // Guard against an over-release (e.g. StrictMode's double-invoke in dev,
  // or a caller bug) taking the counter negative and leaving `locked`
  // permanently false for every subsequent acquire.
  lockCount = Math.max(0, lockCount - 1);
  if (lockCount === 0) {
    document.body.style.overflow = previousOverflow;
  }
}

/**
 * Locks `document.body`'s scroll while `active` is true, and always
 * releases on unmount (React runs an effect's cleanup unconditionally when
 * the component unmounts, whether or not `active` was still true).
 *
 * Ref-counted at module scope: with two simultaneous lockers (e.g. the
 * mobile drawer AND the command palette both open), the body stays locked
 * until the last one releases.
 */
export function useBodyScrollLock(active: boolean): void {
  useEffect(() => {
    if (!active) return;
    acquire();
    return () => release();
  }, [active]);
}
