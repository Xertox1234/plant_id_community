---
status: pending
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

- [ ] Its finding is fixed with a test, or the Work Log records why it was left as is.

## Work Log

### 2026-10-10 - Promoted out of todo 527

- Split from the consolidated follow-up todo 527 (owner decision 2026-10-10: one todo per source PR).
