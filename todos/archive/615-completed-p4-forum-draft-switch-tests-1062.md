---
status: completed
priority: p4
issue_id: "615"
tags: [web, forum, testing, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-11
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

- [x] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-11 - Filed from the PR #1062 review (todo sweep run 2026-10-11-2219)

Filed by the closing step of the run from `state.py followups-md g14`.

### 2026-10-12 - Implemented by the todo sweep (run 2026-10-12-0349)

- Findings 1 and 4 (fixed, test): a new test in `web/src/pages/forum/NewThreadPage.test.tsx` sets choices per voter to 2 and a close time before a switch to a board with a stored draft, then re-enables the poll, fills two options and posts. It asserts the close-time field is blank, choices per voter is 1, and the posted poll is exactly `{question, options}`. Deleting `setPollClosesAt('')` or `setPollMaxChoices(1)` each turns it red (checked by mutation).
- Findings 2 and 6 (declined as a behaviour change, documented): a switch to a board with no stored draft keeps the text by the 2026-10-11 owner decision (todo 575), and the poll and the identification attachment go with that text. The owner decision in todo 597 covers only a switch that loads a draft. A comment next to the `stored === null` branch in `web/src/pages/forum/NewThreadPage.tsx` now says so.
- Findings 2 and 5 (fixed, test): two new tests pin the no-draft branch. The poll (question, options, choices per voter) and the attachment survive the switch and are posted. Moving the reset above the `stored === null` early return turns both red (checked by mutation).
- Finding 3 (fixed, test): the `it.each` rows now carry the expected body, and the non-string title/tags row asserts `<p>kept</p>` is kept. Dropping the body when the title is not a string turns it red (checked by mutation).

### 2026-10-12 - Verified by the todo sweep (run 2026-10-12-0349)

- AC 1: `sh -c "cd web && npx vitest run src/pages/forum/NewThreadPage.test.tsx 2>&1; grep -n -A6 'Implemented by the todo sweep' todos/archive/615-completed-p4-forum-draft-switch-tests-1062.md"` — evidence `.sweep-evidence/g13/615-ac0.txt` (not committed), last lines:

  ```text
  40-
  41-- Findings 1 and 4 (fixed, test): a new test in `web/src/pages/forum/NewThreadPage.test.tsx` sets choices per voter to 2 and a close time before a switch to a board with a stored draft, then re-enables the poll, fills two options and posts. It asserts the close-time field is blank, choices per voter is 1, and the posted poll is exactly `{question, options}`. Deleting `setPollClosesAt('')` or `setPollMaxChoices(1)` each turns it red (checked by mutation).
  42-- Findings 2 and 6 (declined as a behaviour change, documented): a switch to a board with no stored draft keeps the text by the 2026-10-11 owner decision (todo 575), and the poll and the identification attachment go with that text. The owner decision in todo 597 covers only a switch that loads a draft. A comment next to the `stored === null` branch in `web/src/pages/forum/NewThreadPage.tsx` now says so.
  43-- Findings 2 and 5 (fixed, test): two new tests pin the no-draft branch. The poll (question, options, choices per voter) and the attachment survive the switch and are posted. Moving the reset above the `stored === null` early return turns both red (checked by mutation).
  44-- Finding 3 (fixed, test): the `it.each` rows now carry the expected body, and the non-string title/tags row asserts `<p>kept</p>` is kept. Dropping the body when the title is not a string turns it red (checked by mutation).
  ```

### 2026-10-12 - Completed by the todo sweep (run 2026-10-12-0349)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
