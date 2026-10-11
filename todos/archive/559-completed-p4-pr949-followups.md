---
status: completed
priority: p4
issue_id: "559"
tags: [todo-sweep, follow-ups, backend]
dependencies: []
triage: ready
triaged: 2026-10-11
---

# Follow-ups from PR #949 (todo 521), run 2026-10-02-0335

## Problem

Promoted out of todo 527 on 2026-10-10 (owner decision: slice it per PR). Todo-sweep run 2026-10-02-0335
merged PR #949; its review rounds reported the non-blocking findings below, which a curation pass
checked against main and a refuter failed to refute. Line numbers are as of 2026-10-02, so re-check each
finding against main before acting on it.

## Findings

### PR #949 (todo 521)

1. **`backend/packages/wagtail_forum/wagtail_forum/tests/api/test_replies_reactions.py:399`** (low, polish). Lock-window comment and failure message assume counted[0] is recount's own COUNT. `counted` matches any reaction-table SELECT containing COUNT( between the INSERT and the reaction\_counts write, so counted[0] is the first such COUNT, not necessarily recount's. A future receiver or helper that counts reactions before recount's FOR UPDATE would empty recount\_locks and fail with a message blaming Reaction.recount, a case the old counted[-1] bound tolerated. The test is correct today (recount issues the only COUNT), but no comment names this trip-wire.
   Suggested: Extend the 387-395 comment, and correct the 376-377 "recount's aggregate read" line, to say any earlier reaction COUNT in the window also trips this check, so the next developer looks there before changing Reaction.recount.
   Seen on main: test\_replies\_reactions.py:376-377 comment says "recount's aggregate read", but :378-385 keep any SELECT with FROM "\<reaction table>" and COUNT( in inserted[-1] \< i \< written[-1]; :399 `inserted[-1] < i < counted[0]`; :405 message names Reaction.recount. No Reaction-sender receivers in wagtail\_forum/signals.py or forum\_host signals/redirects/forum\_settings.

## Acceptance Criteria

- [x] Its finding is fixed with a test, or the Work Log records why it was left as is.

## Work Log

### 2026-10-10 - Promoted out of todo 527

- Split from the consolidated follow-up todo 527 (owner decision 2026-10-10: one todo per source PR).

### 2026-10-11 - Implemented by the todo sweep (run 2026-10-11-1448)

- Re-checked against main: `Reaction.recount` (`wagtail_forum/models/reactions.py`) still issues the only
  reaction COUNT, and the test's `counted` filter still keeps any reaction COUNT in the INSERT..write window.
- `test_reaction_toggle_recounts_under_a_post_row_lock`: corrected the `counted` comment (it collects every
  reaction COUNT in the window, recount's today) and added a trip-wire comment saying an earlier COUNT from
  other code moves the `counted[0]` bound ahead of recount's lock and fails the check with recount unchanged.
- The failure message now names that second cause and quotes the first COUNT's SQL, so a failure points at
  the real culprit. Test logic is unchanged; `test_replies_reactions.py` passes (16 tests).

### 2026-10-11 - Verified by the todo sweep (run 2026-10-11-1448)

- AC 1: `cd backend && python3 scripts/todos/slot_env.py --main-root . 4 -- backend/venv/bin/python -m pytest backend/packages/wagtail_forum/wagtail_forum/tests/api/test_replies_reactions.py --create-db -q && grep -n 'todo 559' backend/packages/wagtail_forum/wagtail_forum/tests/api/test_replies_reactions.py` — evidence `.sweep-evidence/g5/559-ac0.txt` (not committed), last lines:

  ```text
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================= 16 passed, 3 warnings in 19.43s ========================
  exit=0
  380:    # a serializer) lands here too (todo 559).
  399:    # Trip-wire (todo 559): counted[0] is the first reaction COUNT in the
  ```

### 2026-10-11 - Completed by the todo sweep (run 2026-10-11-1448)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
