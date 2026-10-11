---
status: completed
priority: p4
issue_id: "544"
tags: [forum, web, follow-ups, todo-sweep]
dependencies: []
triage: ready
triaged: 2026-10-10
---

# Follow-ups from PR #991 (todo 538, forum composer TipTap JSON)

## Problem

Todo-sweep run 2026-10-10-2307 merged PR #991. Its two review rounds reported the non-blocking
findings below. The follow-ups curator merged duplicates and confirmed each one is still present on main, and a
refuter dismissed none. Line numbers are as of the PR head, so re-check each against main before acting on it.

## Findings

PR #991 (todo sweep run 2026-10-10-2307, group g2, todos 538); follow-ups: verified.

1. **medium** `web/src/pages/forum/NewThreadPage.tsx:237` The persist guard's 'untouched' check compares title and tags to their mounted values by string value, not 'ever edited'. An edit that returns them to the mounted value (body untouched) skips the write, so the stale mid-edit draft stays stored and comes back on reload. This is a regression: the old effect cleared it. | also: The 'untouched' guard compares title and tags by string value, not identity. If an edit puts the fields back to their mounted values, persisting stops and the stored draft keeps the intermediate text. Example: draft title 'abc', type 'd' (saved 'abcd'), backspace: 'abcd' comes back on reload. (reported at line 236) | The untouched-composer guard compares by value, so it also fires on a revert. Type a title, let it persist, clear it back to the mounted '' with body unchanged: the stale draft stays in storage. (reported at line 246) | Fresh composer, type 'x' in the title, delete it: the draft keeps {title:'x'} and comes back on revisit. A user who clears the form never gets the draft removed. Typing 'secret' and clearing it keeps 'secret'.
2. **low** `web/src/pages/forum/NewThreadPage.test.tsx:558` The todo-538 test covers only 'untouched, then the first edit persists'. No test pins edit-then-revert, the case the value-equality guard gets wrong, so that regression passes CI.
3. **low** `web/src/pages/forum/ThreadDetailPage.tsx:1351` The reply onChange draft writer and the NewThreadPage persist effect moved from isBlankDoc to isEmptyDoc, so an image-only draft is now kept. No test drives either path; only the Quote path is covered.
4. **low** `web/src/utils/forumBody.ts:112` isBlankDoc memoises per document object in a WeakMap on the assumption that docs are never mutated in place. Only a comment enforces this, so an in-place edit of a state doc would return a stale answer.
5. **low** `web/src/pages/forum/ThreadDetailPage.tsx:606` The reflowed handleQuote comment leaves an over-long line ('...content and quoting must keep it (todo 538). TipTap's `content` is init-only, so the composer is'), which breaks the wrap the rest of the block uses. Cosmetic only, since Prettier does not reflow comments. | also: Comment re-flow left an over-long line ('...content. Quoting must keep it (todo 538). TipTap's `content` is init-only...'), which will fail the Prettier check if it applies to comments. (reported at line 319; it is the same handleQuote comment)
6. **low** `web/src/pages/forum/NewThreadPage.test.tsx:162` A comment line runs far past the wrapping width because a sentence ('Owner decision 2026-10-10: log...') was joined onto the previous line. Prettier does not reflow comments, so it stays. | also: Comment line runs past the prettier width: a sentence was joined onto the previous line ('...silently delete the stored draft. Owner decision 2026-10-10: log...').

## Acceptance Criteria

- [x] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason.

## Work Log

### 2026-10-10 - Implemented by the todo sweep (run 2026-10-11-0149)

- Finding 1 fixed: `web/src/pages/forum/NewThreadPage.tsx` latches a `touchedRef` on the first change, so an
  edit undone back to the mounted value still persists (a cleared form removes the draft; 'abcd' then
  backspace stores 'abc'). Two new tests in `NewThreadPage.test.tsx`, both failing on the old guard (finding 2).
- Finding 3 fixed: new tests pin the image-only draft for the new-thread persist effect and the reply
  onChange writer (`ThreadDetailPage.test.tsx`), which also checks Post Reply stays disabled.
- Findings 5 and 6 fixed: re-wrapped the over-long `handleQuote` comment and the owner-decision test comment.
- Finding 4 declined: TipTap's `getJSON()` returns a fresh object per transaction and both pages only replace
  state, never mutate it; a runtime guard (deep-freeze or re-check) would cost the per-keystroke serialisation
  the cache exists to save. The invariant stays documented at `blankDocCache` in `web/src/utils/forumBody.ts`.

### 2026-10-10 - Verified by the todo sweep (run 2026-10-11-0149)

- AC 1: `bash -c 'cd web && npx vitest run src/pages/forum/NewThreadPage.test.tsx src/pages/forum/ThreadDetailPage.test.tsx src/utils/forumBody.test.ts 2>&1 | grep -E "todo 544|Test Files|Tests "; grep -nE "^- Finding" todos/archive/544-completed-p4-forum-composer-pr991-followups.md'` — evidence `.sweep-evidence/g1/544-ac0.txt` (not committed), last lines:

  ```text
        Tests  213 passed (213)
  39:- Finding 1 fixed: `web/src/pages/forum/NewThreadPage.tsx` latches a `touchedRef` on the first change, so an
  42:- Finding 3 fixed: new tests pin the image-only draft for the new-thread persist effect and the reply
  44:- Findings 5 and 6 fixed: re-wrapped the over-long `handleQuote` comment and the owner-decision test comment.
  45:- Finding 4 declined: TipTap's `getJSON()` returns a fresh object per transaction and both pages only replace
  ```

### 2026-10-10 - Completed by the todo sweep (run 2026-10-11-0149)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
