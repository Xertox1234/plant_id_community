---
status: completed
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

- [x] `max_choices` on `Poll`; API accepts array votes, enforces ≤ max
      (test-pinned, including downgrade/upgrade edge cases)
- [x] Change-vote semantics decided + test-pinned
- [x] Web checkbox voting + results; Flutter multi-choice from wave 3

## Work Log

### 2026-09-04 - Filed

- Surfaced by the 2026-09-04 forum competitive assessment (smaller-misses:
  multi-choice polls).

### 2026-09-04 - Started by completing-todos skill (run 2026-09-05-0408)

- Picked up by automated workflow.

### 2026-09-05 - Design decisions (run 2026-09-05-0408)

- **Change-vote: NO — one final submission per voter, for single- and
  multi-choice polls alike.** The todo-283 decision (reject, never replace)
  carries over rather than adopting Discourse's change-vote: results are
  hidden until you vote, so a change-vote would let a voter peek at the
  tally and re-decide, defeating the anti-anchoring rule. A second
  submission of any size is 409 (no top-up, no merge); the message names the
  existing choice(s). Revisit trigger: if results ever become visible before
  voting, change-vote becomes viable and this decision should be re-taken.
- **Storage:** `PollVote` unique on `(poll, user, option)` — one row per
  picked option, so `Poll.results` stays row-based. "One submission" moved
  from the old `(poll, user)` constraint into `PollVoteView`: a per-poll
  `select_for_update` lock + an already-voted check + `bulk_create` of the
  ballot in one transaction, so two concurrent submissions from one user
  serialize (the second sees the first's rows → 409).
- **`total_votes` = distinct voters**, not rows: in a multi-choice poll the
  option counts can sum past it; each bar is "share of voters who picked
  this". The distinct count costs one extra query and is paid ONLY by
  `max_choices > 1` polls, so the single-choice query pins are untouched.
- **Contract:** `option_ids` list (1..`max_choices`); `option_id` accepted
  as the single form; `my_vote_option_ids` (list, empty = not voted)
  replaces `my_vote_option_id`; `max_choices` on the poll payload and on
  the create payload (omitted = 1; must be ≤ non-blank options). Whole
  ballot accepted or refused — nothing partial.
- **Web:** checkbox ballot capped in the UI at `max_choices`, one Vote
  button; the composer's "Choices per voter" is a `<select>` bounded by the
  filled option count (a controlled number input snaps to its fallback on
  clear and turns "2" into "12").
- **Flutter:** no poll UI exists yet; multi-choice rolls into todo 341
  wave 3 as the todo prescribes (build it multi-choice from the start).

### 2026-09-05 - Verification evidence (run 2026-09-05-0408)

- AC1 `max_choices` + array votes ≤ max: migration
  `0028_poll_max_choices_and_multi_vote` (AddField + constraint swap to
  `(poll, user, option)`); `test_polls_api.py` —
  `test_compose_a_multi_choice_poll_stores_max_choices`,
  `test_max_choices_defaults_to_single_choice`,
  `test_invalid_max_choices_is_rejected_and_creates_no_topic` (3 cases:
  above option count, blanks don't count, zero),
  `test_multi_choice_vote_records_each_option_and_counts_the_voter_once`,
  `test_a_ballot_with_more_choices_than_allowed_is_rejected_whole`,
  `test_a_single_choice_poll_rejects_a_two_option_ballot` (the downgrade
  edge: every pre-349 poll keeps its exact contract),
  `test_malformed_ballots_are_rejected` (3 cases),
  `test_repeating_an_option_or_mixing_the_two_forms_is_rejected`,
  `test_a_ballot_with_a_foreign_option_is_rejected_whole`;
  `test_polls.py` — constraint test rewritten for `(poll, user, option)` +
  `test_multi_choice_results_count_voters_once_but_every_option_they_picked`.
- AC2 change-vote decided (REJECT, see the decisions entry) + pinned:
  `test_second_submission_on_a_multi_choice_poll_is_rejected_not_merged`
  (409, rows unchanged, totals unmoved) alongside the pre-existing
  single-choice `test_second_vote_by_same_user_is_rejected_not_replaced`.
- AC3 web: `PollCard.test.tsx` +4 (checkbox ballot, cap at max_choices,
  array submit + per-option "your vote", voted state),
  `NewThreadPage.test.tsx` +1 (`max_choices` only when > 1; Post gated
  when it exceeds the filled options), `ThreadDetailPage.test.tsx` updated.
  Flutter: deferred to todo 341 wave 3 per this AC's own wording (no poll
  UI exists on mobile yet).
- Mutation check: with the `max_choices` cap and the already-voted check
  both removed, `3 failed` (the two tests above + the single-choice 409
  test); restored from a copy → guard present, `MUTANT` count 0.
- Evidence: poll suites on a fresh DB `91 passed` + `11 passed`; full
  backend suite `2062 passed, 8 skipped in 281.57s`; web `tsc --noEmit`
  clean, ESLint clean, Prettier clean, touched files `104 passed`, full
  web suite `1080 passed (90 files)`.

### 2026-09-05 - Code review round 1 + repair (run 2026-09-05-0408)

- Reviewers: django-drf, react-typescript, cross-cutting (read-only,
  parallel). **Nothing blocking**; 11 findings (0 high) — all repaired:
- django-drf MEDIUM: `results()` summed option counts for single-choice
  polls, trusting a view-level invariant. Now the distinct-voter total rides
  the options query as a correlated subquery for EVERY poll — still one
  query (`test_multi_choice_poll_costs_no_more_queries_than_single_choice`).
- django-drf LOW: vote response now sorts the ballot ids like `get_poll`
  reads them back (`sorted(...)`); serializer message split ("Choose at least
  one option." vs "not both"); type hints on `_already_voted_message`;
  `get_poll` cost docstring updated; migration carries a rollback note
  (INFO: reverse fails once multi-choice ballots exist).
- react MEDIUM: composer select value is `effectiveMaxChoices =
  min(pollMaxChoices, filled options)` — the value the select shows, the
  payload sends and the server accepts (test pins the clamp: 3 → 2 when an
  option is blanked). react LOW: capped checkboxes use `aria-disabled` + a
  no-op and `aria-describedby` the cap hint, staying in the tab order.
- cross-cutting MEDIUM: `option_ids` is a `_BoundedBallotListField`
  (raw-length gate before per-item parsing,
  `test_an_oversized_ballot_is_refused_before_per_item_parsing`); the
  duplicate-option test asserts the validator's own text; the lock is now
  testable — fast unlocked check + locked re-check, pinned by
  `test_locked_recheck_refuses_a_ballot_the_fast_path_missed` (monkeypatched
  miss-once, test_collections precedent) and
  `test_a_ballot_is_written_under_a_poll_row_lock` (`FOR UPDATE` in the
  captured SQL). cross-cutting LOW: query-count pin above.
- Post-repair: poll suites + topic detail + mounted + schema `95 passed`
  (one order-dependent flake in `test_topic_detail.py::…is_bookmarked…`
  passed alone and on a file rerun, 21/21 — unrelated to polls); web
  `104 passed`, tsc/eslint/prettier clean. Residue sweep clean.
- Post-repair full backend suite: `2066 passed, 8 skipped in 264.94s`.

### 2026-09-04 - Completed by completing-todos skill (run 2026-09-05-0408)

- Verification: all 3 acceptance criteria passed (Flutter half deferred to todo 341 wave 3 per the AC's own wording); full backend suite 2066 passed, web suite 1080 passed.
- Review: 11 findings across three reviewers, 0 blocking — all 11 repaired in round 1.
