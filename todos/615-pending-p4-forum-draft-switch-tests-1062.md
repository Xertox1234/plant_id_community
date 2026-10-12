---
status: pending
priority: p4
issue_id: "615"
tags: [web, forum, testing, follow-ups]
dependencies: []
---

# Follow-ups from PR #1062 (todo 597, forum draft switch on category change)

## Problem

Todo-sweep run 2026-10-11-2219 merged PR #1062 (todo 597, forum draft switch on category change). The non-blocking review findings are below. The curator merged duplicates and checked each item against main, and the refuter dismissed what is listed as dropped. An item the curator did not return was kept as stored, unchecked. Line numbers are as of the PR head, so re-check each against main before acting on it.

## Findings

PR #1062 (todo sweep run 2026-10-11-2219, group g14, todos 597); follow-ups: verified; 3 item(s) the curator did not return were kept as stored.

1. **low** `web/src/pages/forum/NewThreadPage.test.tsx:806` The poll-reset test checks only pollEnabled, the question and the two options. Nothing asserts the setPollClosesAt('') and setPollMaxChoices(1) resets, so deleting either line still passes. The submit assertion is vacuous for the poll because the toggle is off at submit. | also: web/src/pages/forum/NewThreadPage.test.tsx:842 The poll-reset test checks only the poll question and options after the board switch. NewThreadPage also holds pollClosesAt and pollMaxChoices state, so a missing reset of those would pass.
2. **low** `web/src/pages/forum/NewThreadPage.tsx:293` The poll and identification reset runs only in the 'new board has a stored draft' branch. On a switch to a board with no draft (stored === null), the title/body, poll and photo all carry over. That is consistent for the text, but the poll/photo carry-over is untested and undocumented next to the reset comment. | also: web/src/pages/forum/NewThreadPage.tsx:300 The poll and attachment reset runs only when the new board has a stored draft. On a switch to a board with no draft, board A's text, poll and photo carry over, which is inconsistent with the reset's stated rationale. Nit. | web/src/pages/forum/NewThreadPage.test.tsx:805 The work log says a switch to a board with NO stored draft keeps the poll and the attachment (owner decision), but no test covers that branch. Moving the reset above the `stored === null` early return would pass every test.
3. **low** `web/src/pages/forum/NewThreadPage.test.tsx:855` The it.each case 'a non-string title and tags' stores body `'<p>kept</p>'` but never asserts that the body is kept, so dropping the body fallback would not turn this case red.
4. **low** `web/src/pages/forum/NewThreadPage.test.tsx:842` The poll-reset test checks only the poll question and options after the board switch. NewThreadPage also holds pollClosesAt and pollMaxChoices state, so a missing reset of those would pass.
5. **low** `web/src/pages/forum/NewThreadPage.test.tsx:805` The work log says a switch to a board with NO stored draft keeps the poll and the attachment (the earlier owner decision), but no test covers that branch. A later change that moves the reset above the `stored === null` early return would pass every test.
6. **low** `web/src/pages/forum/NewThreadPage.tsx:300` The poll and attachment reset runs only when the new board has a stored draft. On a switch to a board with no draft (stored === null branch), board A's text, poll and photo all carry over, so the reset is inconsistent with its stated rationale. This is consistent for the text, so it is only a nit.

## Acceptance Criteria

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-11 - Filed from the PR #1062 review (todo sweep run 2026-10-11-2219)

Filed by the closing step of the run from `state.py followups-md g14`.
