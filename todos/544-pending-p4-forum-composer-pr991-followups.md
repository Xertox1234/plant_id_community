---
status: pending
priority: p4
issue_id: "544"
tags: [forum, web, follow-ups, todo-sweep]
dependencies: []
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

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason.

## Work Log
