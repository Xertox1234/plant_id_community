---
status: pending
priority: p4
issue_id: "575"
tags: [forum, web, follow-ups, todo-sweep]
dependencies: []
---

# Follow-ups from PR #1014 (todo 549, forum composer draft key)

## Problem

Todo-sweep run 2026-10-11-0401 merged PR #1014. Its two review rounds reported the non-blocking
findings below. The follow-ups curator merged duplicates and checked each one against main, and a refuter
tried to refute every one; anything dropped is listed with its reason. Line numbers are as of the PR head,
so re-check each against main before acting on it.

## Findings

PR #1014 (todo sweep run 2026-10-11-0401, group g3, todos 549); follow-ups: verified; 3 item(s) the curator did not return were kept as stored.

1. **medium** `web/src/pages/forum/NewThreadPage.tsx:256` On a ?category= change the guard only re-arms the baseline; board B's stored draft is never loaded into the form (useState initializers don't re-run), so the next keystroke writes board A's leftover text over B's unseen draft. The loss is delayed one edit, not fixed, and the test pins it. | also: On a ?category= change the form keeps board A's text and B's stored draft is never loaded, so the user's next keystroke on B overwrites B's draft. The fix only delays the data loss by one edit, and the new test at NewThreadPage.test.tsx (typing 'y' replaces 'Board B words') makes that loss expected behaviour. | After a ?category= change, the form keeps board A's text and does not load board B's stored draft. The guard only holds until the next keystroke, which then overwrites B's draft with A's text plus the edit. The new test codifies this ('the user's next edit is theirs to keep'). | Re-arming the baseline on a ?category= change only delays the overwrite by one keystroke. A user who had saved text on board B loses it. | NewThreadPage.tsx:255 On a ?category= change the guard only re-arms. Board B's stored draft is never loaded, because the useState initializers do not re-run, so the next keystroke on board A's leftover text overwrites board B's draft. | NewThreadPage.test.tsx:680 The 're-arms per key' test asserts that typing 'y' replaces board B's stored draft ('Board B words'). That pins the lossy behaviour as correct, and no test checks that board B's draft appears in the form after the switch.
2. **medium** `web/src/pages/forum/NewThreadPage.test.tsx:702` The 'does not copy a touched form into the new board key' test ends on an absence assertion (loadDraft(keyB) is null) right after waiting only for fetchCategory and never edits after the switch, so a late save effect or a guard that skips just one run would still pass. | also: NewThreadPage.test.tsx:688 The 'does not copy a touched form' test only checks that keyB is still null right after the rerender. It never makes an edit after the switch, so it would also pass if the guard only skipped the first effect run, and it does not cover what is written to keyB on the next keystroke.
3. **medium** `web/src/pages/forum/NewThreadPage.tsx:255` On a ?category= change the guard only re-arms. Board B's stored draft is never loaded, because the useState initializers do not re-run, so the next keystroke on board A's leftover text overwrites board B's draft. The data loss is delayed by one edit, not fixed. | also: A ?category= change only postpones the overwrite. The form still shows board A's text and B's stored draft is never loaded, so the next keystroke saves A's text plus that keystroke over B's draft. The new test at NewThreadPage.test.tsx ~684 asserts exactly this ('Board B words' lost).
4. **medium** `web/src/pages/forum/NewThreadPage.test.tsx:680` The 're-arms per key' test asserts that typing 'y' replaces board B's stored draft ('Board B words'). That pins the lossy behaviour as correct, and no test checks that board B's draft appears in the form after the switch. | also: The new test asserts the data-loss path as intended behaviour. After the switch, typing 'y' writes {title:'y'} over board B's stored 'Board B words' draft, which the user never saw, and the test passes on that overwrite. The other edits to this file only add assertions and are justified.
5. **low** `web/src/pages/forum/NewThreadPage.test.tsx:610` Verification note, not a defect: the only change to an existing test adds an assertion that an image-only body keeps Post disabled (isBlankDoc); the other four tests are new and none weakens an existing assertion.
6. **low** `web/src/pages/forum/NewThreadPage.test.tsx:688` The 'does not copy a touched form' test only checks that keyB is still null right after the rerender. It never makes an edit after the switch, so it would also pass if the guard only skipped the first effect run, and it does not cover what is written to keyB on the next keystroke.

Dropped by curation (fixed on main, refuted, or not a reported location):

- low: web/src/pages/forum/NewThreadPage.test.tsx:615 The Post-disabled assertion for the image-only body has no enabled counterpart, so it may not fail if isBlankDoc is swapped for isEmptyDoc when the button is disabled for some other reason. (refuted: In that test the other Post gates are met: category loaded ('Plant Care' found), title typed, poll off. Swapping in isEmptyDoc would enable Post (image body isn't empty), so toBeDisabled fails. Other tests (line 852 toBeEnabled, submits at 750/783/820) show Post enabled with a text body.)

## Acceptance Criteria

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason.

## Work Log
