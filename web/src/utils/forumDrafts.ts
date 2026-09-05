/**
 * Best-effort composer draft persistence (sessionStorage — survives navigation
 * within the tab, intentionally not across sessions). All storage failures are
 * swallowed: drafts are a convenience, never a correctness dependency.
 */

const PREFIX = 'forum-draft:';

export function draftKey(kind: 'reply' | 'new-thread', id: string): string {
  return `${PREFIX}${kind}:${id}`;
}

export function loadDraft(key: string): string | null {
  try {
    return sessionStorage.getItem(key);
  } catch {
    return null;
  }
}

export function saveDraft(key: string, value: string): void {
  try {
    if (value) {
      sessionStorage.setItem(key, value);
    } else {
      sessionStorage.removeItem(key);
    }
  } catch {
    /* private mode / quota — best-effort only */
  }
}

export function clearDraft(key: string): void {
  try {
    sessionStorage.removeItem(key);
  } catch {
    /* ignore */
  }
}

/**
 * Drop every composer draft in this tab. Keys are scoped by topic/board, not
 * by user, and sessionStorage outlives a logout — so without this a shared-
 * device logout → login-as-someone-else in the same tab would pre-fill the
 * next user's composer with the previous user's unsent text (audit
 * 2026-09-04 L4). Called from authService.logout().
 */
export function clearAllDrafts(): void {
  try {
    const stale: string[] = [];
    for (let i = 0; i < sessionStorage.length; i += 1) {
      const key = sessionStorage.key(i);
      if (key?.startsWith(PREFIX)) stale.push(key);
    }
    stale.forEach((key) => sessionStorage.removeItem(key));
  } catch {
    /* ignore */
  }
}
