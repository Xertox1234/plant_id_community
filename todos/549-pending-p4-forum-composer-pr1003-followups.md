---
status: pending
priority: p4
issue_id: "549"
tags: [forum, web, follow-ups, todo-sweep]
dependencies: []
---

# Follow-ups from PR #1003 (todo 544, forum composer draft persist)

## Problem

Todo-sweep run 2026-10-11-0149 merged PR #1003. Its two review rounds reported the non-blocking
findings below. The curator merged duplicates and confirmed each item is still on main; the refuter dismissed one (listed below). Line numbers are as of the PR head, so re-check each against main before acting on it.

## Findings

PR #1003 (todo sweep run 2026-10-11-0149, group g1, todos 544); follow-ups: verified; 1 item(s) the curator did not return were kept as stored.

1. **medium** `web/src/pages/forum/NewThreadPage.tsx:242` touchedRef stays latched when newThreadDraftKey changes without a remount (route stays mounted across ?category changes via AppShell/CommandPalette 'Start a thread'). A touched form reverted to empty then runs saveDraft(newKey, '') and deletes the other board's draft. | also: touchedRef never resets when newThreadDraftKey changes. If the user types and then clears the form, a later in-place ?category= change runs the effect with isEmpty and calls saveDraft(newKey, ''), deleting the other board's stored draft. Before this change the effect returned early because the values equalled mounted. | low @241: touchedRef never resets when newThreadDraftKey changes. The route has no key, so the AppShell 'Start a thread' link (/forum/new-thread) can change ?category= without a remount. After a type-then-revert, the effect then writes or removes the draft under the new key, where the old value check returned early. | low @241: The AppShell or palette link to /forum/new-thread keeps the page mounted, so after an edit-then-revert the effect copies A's form into the 'unknown' key, or deletes that draft if the form is empty. The old guard skipped this write.
2. **low** `web/src/pages/forum/NewThreadPage.test.tsx:611` Image-only draft test asserts the draft is kept but not that the submit gate (isBlankDoc) still treats the body as blank, unlike the ThreadDetailPage twin; the isEmptyDoc vs isBlankDoc split is only half pinned.
3. **low** `web/src/pages/forum/NewThreadPage.test.tsx:593` The 'stores the reverted value' test relies on a mid-sequence 'abcd' assertion and covers only the title field; reverting via the body or tags field to the mounted value is not covered.
4. **low** `web/src/pages/forum/NewThreadPage.tsx:241` touchedRef never resets when newThreadDraftKey changes. The route has no key, so the AppShell 'Start a thread' link (/forum/new-thread) can change ?category= without a remount. After a type-then-revert, the effect then writes or removes the draft under the new key, where the old value check returned early. | also: touchedRef never resets when newThreadDraftKey changes. The AppShell or palette link to /forum/new-thread keeps the page mounted, so after an edit-then-revert the effect copies A's form into the 'unknown' key, or deletes that draft if the form is empty. The old guard skipped this write.

Dropped by curation (fixed on main, refuted, or not a reported location):

- low: web/src/pages/forum/NewThreadPage.test.tsx:525 Edits to existing tests checked: NewThreadPage.test.tsx only re-wraps a comment and adds three new tests; ThreadDetailPage.test.tsx only adds one test. No existing assertion was weakened or removed. (refuted: Not a defect: the item itself states no existing assertion was weakened or removed, and the origin/main test file confirms only new todo-544 tests were added after the todo-538 test. There is nothing to fix or follow up.)

## Acceptance Criteria

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason.

## Work Log
