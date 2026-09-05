---
status: pending
priority: p4
issue_id: "349"
tags: [forum, polls, package, web, flutter]
dependencies: []
---

# Multi-choice polls (N-of-K votes) extending the single-choice poll

## Problem

Polls shipped single-choice only (todo 309 / audit M8, PR #589): one poll
per topic, one vote per user
(`wagtail_forum/models/polls.py:1-175`). Community staples ("which of these
three pests have you seen this year?") need multi-select. Every competing
forum supports it.

## Findings

- Current uniqueness is enforced per `(poll, user)` in `PollVote`; results
  aggregated from rows (`wagtail_forum/api/polls.py:1-102`).
- Polls are immutable after creation; closing returns 409.
- Web UI: `PollCard.tsx:107-187` (radio-style vote + results bars).
  Flutter: no poll UI yet (todo 341 wave 3).

## Recommended Action

1. **Package (`wagtail_forum`):** add `Poll.max_choices` (default 1 = current
   behavior; migration is additive). Vote contract change: accept an option
   id **list** for `max_choices > 1`; validate ≤ max_choices; each
   selection still one `PollVote` row (unique `(poll, user, option)`) so
   recounting stays row-based and change-vote becomes replace-set semantics.
2. Decide and record: can a voter change their vote before close? (Current
   duplicate returns 409 — keep 409 for exact-duplicate, add retract/
   replace only if cheap; Discourse allows change-vote.)
3. **Web:** checkbox rendering when `max_choices > 1`; submit-array call.
4. **Flutter:** rolls into todo 341 wave 3 — build multi-choice from the
   start there so mobile never ships the single-choice-only variant.

## Technical Details

- Existing endpoints/limits: `topic-poll-vote` POST,
  `topic-poll-create` at topic creation; rate limits in
  `apps/forum_host/constants.py:15-91`.
- Hidden-topic exclusion already handled in poll visibility
  (`wagtail_forum/api/polls.py`).
- Keep the one-poll-per-topic constraint.

## Acceptance Criteria

- [ ] `max_choices` on `Poll`; API accepts array votes, enforces ≤ max
      (test-pinned, including downgrade/upgrade edge cases)
- [ ] Change-vote semantics decided + test-pinned
- [ ] Web checkbox voting + results; Flutter multi-choice from wave 3

## Work Log

### 2026-09-04 - Filed

- Surfaced by the 2026-09-04 forum competitive assessment (smaller-misses:
  multi-choice polls).
