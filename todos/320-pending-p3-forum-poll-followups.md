---
status: pending
priority: p3
issue_id: "320"
tags: [forum, web, api]
dependencies: []
source_review: "todo 309 (deferred 2026-08-30); PR #589 /code-review medium (2026-08-30)"
---

# Forum polls: raw DRF validation-error envelope leaks to the user (cross-cutting, not poll-specific)

## Problem

Originally 8 findings across two review passes on todo 309 (forum polls).
7 of the 8 were fixed directly in PR #589 once the user asked for the
review's fixes to be applied (see Work Log) — only this one remains open,
deliberately: it is a pre-existing, cross-cutting infra issue shared by
every DRF endpoint in the repo, not something scoped to the poll feature,
and fixing it properly means auditing every page that renders `err.message`
verbatim across `web/src/`. That is a different, wider PR than this one.

## Findings

- **Raw DRF validation-error dict leaks to the user on ANY nested-serializer
  400**, not just polls. `backend/apps/core/exceptions.py:151` sets
  `"message": str(exc)` for any DRF exception carrying a `response` — for a
  nested serializer's `ValidationError` (e.g. `TopicPollSerializer`'s), `str(exc)`
  stringifies the whole `detail` dict including `ErrorDetail(...)` reprs, not
  a clean sentence. `web/src/services/forumService.ts:96-100`
  (`authenticatedFetch`) takes `error.message` straight from that envelope
  and every page-level `catch` (e.g. `NewThreadPage.tsx`) renders it
  verbatim. Confirmed reachable via the poll composer (a validation error
  that reaches the server despite todo 309's client-side `pollValid` gate —
  e.g. a duplicate-option or too-long-question poll, which the client
  doesn't pre-validate), but the root cause is generic to every
  nested-serializer field on every endpoint, not poll-specific.

## Recommended Action

Either (a) have `apps/core/exceptions.py` format a nested `ValidationError`'s
`detail` into a flat, readable string (walk the dict, join field:message
pairs) instead of `str(exc)`, or (b) have the frontend's `authenticatedFetch`
prefer a structured `errors` field over `message` when the backend supplies
one, falling back to `message` only when it doesn't. Whichever direction,
this is a shared-infra change — audit every page that renders `err.message`
verbatim before shipping, not just the forum composer.

## Technical Details

- `backend/apps/core/exceptions.py` (custom DRF exception handler).
- `web/src/services/forumService.ts` (`authenticatedFetch`, `ForumApiError`).
- `web/src/pages/forum/NewThreadPage.tsx` (one of several call sites that
  would benefit, not the only one — grep `err.message`/`error.message`
  across `web/src/pages/` and `web/src/components/` for the full blast
  radius before scoping the fix).

## Acceptance Criteria

- [ ] A nested-serializer validation error (poll or otherwise) renders a
      readable message to the user, not a raw Python dict repr — test
      asserting the rendered text contains no `ErrorDetail`/`{'...':` markup

## Notes

p3. Not a live vulnerability or data-corruption risk — UX polish (a raw
dict repr instead of a clean sentence on an already-rare validation
failure). Deferred out of todo 309 / PR #589 per this project's
review-round discipline (fix BLOCKING findings in round 1, non-blocking
findings become a follow-up todo rather than a third review round).

## Work Log

### 2026-08-30 - 7 of 8 findings fixed directly, on user request

The user asked to apply the review's fixes rather than defer them further.
Verified each of the 7 was safe to fix without expanding scope beyond the
poll feature (unlike #1 above) before doing so:

- **PollCard resync** (was #2): added a `useEffect` in `PollCard.tsx`
  tracking the `poll` prop via a `useRef`, resyncing `current` only when
  the prop's IDENTITY changes (a real parent refetch) and no vote is in
  flight (`pendingOptionId === null`) — deliberately NOT keyed off `current`
  in the deps array, since that would re-fire immediately after
  `handleVote` sets `current` and stomp the just-applied vote result with
  the pre-vote prop. Two new tests in `PollCard.test.tsx`: one asserting a
  same-thread prop change updates displayed counts, one specifically
  asserting a successful vote survives an unrelated refetch that itself
  now includes the vote (not assumed — asserted).
- **Payload duplication + weak drift test** (was #3): added
  `Poll.serialize(my_vote_option_id)` in `models/polls.py` as the one
  shared shape; `TopicDetailSerializer.get_poll` and `PollVoteView.post`
  both call it now instead of hand-building the dict twice. Strengthened
  `test_vote_response_matches_topic_detail_poll_shape` to
  `assert vote_resp.data == detail_resp.data["poll"]` (full equality, not
  key-set plus two scalars).
- **Extra query** (was #4): closed by the same `Poll.serialize` change —
  `PollVoteView.post` now passes `option.id` (already in scope from the
  just-recorded vote) instead of re-querying `PollVote`.
  `_poll_payload`/`_poll_payload`'s old query is gone entirely.
- **Client/server option-bounds drift** (was #5): added
  `test_poll_option_bounds_defaults_match_the_web_composer_constants` in
  `test_polls_api.py`, pinning `POLL_MIN_OPTIONS == 2` /
  `POLL_MAX_OPTIONS == 10` with an assertion message naming
  `NewThreadPage.tsx`'s constants directly, so a future default change
  fails loudly and points at the other side.
- **Bounded-list duplication** (was #6): factored `_BoundedListField` as a
  shared base (`max_items` + `too_many_message` class attributes) in
  `serializers.py`; `_BoundedTagListField`, `_BoundedCandidateListField`,
  and `_BoundedOptionListField` are now one-line subclasses. Full
  `apps/forum_host packages/wagtail_forum` suite re-run clean afterward
  (tag and candidate tests included, not just poll tests).
- **`closes_at` UI** (was #7): added a `type="datetime-local"` input
  (labeled "Closes (optional)") to the poll composer in `NewThreadPage.tsx`
  — `type="date"` was deliberately rejected: the field is a `DateTimeField`
  compared against `timezone.now()` server-side, and a date-only value
  would submit local midnight, which can already be in the past. The
  submitted local value is converted with `new Date(value).toISOString()`
  before it reaches the API. Two new tests in `NewThreadPage.test.tsx`:
  one asserting a filled-in close time reaches `createThread` as a UTC ISO
  string, one asserting a blank field omits `closes_at` entirely (not an
  empty string).
- **Poll/option invariant** (was #8): added `PollVote.clean()` in
  `models/polls.py`, raising when `option.poll_id != poll_id`.
  Deliberately **NOT** wired into `save()` — Django 6's `full_clean()` also
  runs `validate_constraints()`, which would pre-check `uniq_poll_vote`
  against the DB and convert a double-vote from the `IntegrityError`
  `PollVoteView.post` specifically catches (to return 409) into an
  uncaught pre-save `ValidationError` (500). `clean()` alone protects any
  OTHER writer (Django admin, a data migration, a future second view) that
  calls it explicitly, without touching the one hot path that doesn't. New
  test `test_poll_vote_clean_rejects_option_from_another_poll` calls
  `clean()` directly on a mismatched poll/option pair and asserts it
  raises.

Verification: `pytest apps packages` full suite (matches CI scope, not
just the forum subset) green; `npx vitest run` 979 passed (up from 975);
`npx tsc --noEmit` clean; `npx eslint` clean on all touched files;
`python manage.py check` clean; `makemigrations --check --dry-run` — no
changes detected (both fixes are behavior-only, no schema change).

Advisor consulted before implementing (caught two real mistakes before
they shipped): the Django-6 `full_clean()`/`validate_constraints()`
interaction with the 409 path above, and confirmed the `useRef`-based
`PollCard` resync guard (my own first draft, which included `current` in
the effect's deps, would have immediately reverted a successful vote —
caught and fixed before writing any test against it).
