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
