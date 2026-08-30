---
status: pending
priority: p3
issue_id: "320"
tags: [forum, web, api]
dependencies: []
source_review: "todo 309 (deferred 2026-08-30); PR #589 /code-review medium (2026-08-30)"
---

# Forum polls: eight deferred review findings (error envelope, resync, payload duplication, config drift, DRY, closes_at UI, vote/option invariant)

## Problem

Eight findings across two review passes on todo 309 (forum polls) that were
deliberately NOT fixed there. The first two surfaced during
`react-typescript-reviewer`'s review before merge — one because it's a
pre-existing, cross-cutting infra issue well outside a single feature's
surgical scope; the other because it's a narrow, non-corrupting edge case
where a rushed fix risked introducing a new bug. The remaining six surfaced
from `/code-review medium PR #589` after the PR was opened — none reachable
through a currently-live code path (verified below), so none met this
project's round-1 BLOCKING bar; all are legitimate cleanup/hardening for a
follow-up rather than reasons to hold the PR.

## Findings

- **Raw DRF validation-error dict leaks to the user on ANY nested-serializer
  400**, not just polls. `backend/apps/core/exceptions.py:151` sets
  `"message": str(exc)` for any DRF exception carrying a `response` — for a
  nested serializer's `ValidationError` (e.g. `TopicPollSerializer`'s), `str(exc)`
  stringifies the whole `detail` dict including `ErrorDetail(...)` reprs, not
  a clean sentence. `web/src/services/forumService.ts:96-100`
  (`authenticatedFetch`) takes `error.message` straight from that envelope
  and every page-level `catch` (e.g. `NewThreadPage.tsx:247`) renders it
  verbatim. Confirmed reachable via the poll composer (a validation error
  that reaches the server despite todo 309's new client-side
  `pollValid` gate — e.g. a duplicate-option or too-long-question poll,
  which the client doesn't pre-validate), but the root cause is generic to
  every nested-serializer field on every endpoint, not poll-specific.
  Todo 309's own fix only prevents the ONE most likely trigger (blank
  poll); it does not touch this shared envelope.
- **`PollCard`'s local snapshot doesn't resync on a same-thread data
  refresh.** `web/src/components/forum/PollCard.tsx:34` —
  `useState<ThreadPoll>(poll)` seeds once. `key={thread.poll.id}`
  (`ThreadDetailPage.tsx`) correctly remounts on cross-thread navigation,
  but NOT on a same-thread refetch where `poll.id` is unchanged (e.g.
  `handleBlockAuthor`/`handleUnblockAuthor` bump `reloadKey`, refetching
  `thread` including its poll). If someone else voted in the interim, the
  mounted `PollCard` keeps showing its stale local counts until the
  viewer's own vote (or an actual remount) replaces them. Narrow and
  non-corrupting — counts go stale, never wrong-shaped — but the `key`'s
  actual coverage is narrower than the code comment at
  `ThreadDetailPage.tsx:907-911` implies.
- **Vote response payload hand-duplicates `TopicDetailSerializer.get_poll()`'s
  shape, weakly guarded.** `backend/packages/wagtail_forum/wagtail_forum/api/polls.py:108`
  — `PollVoteView._poll_payload()` builds the same 6-field dict shape a
  second time by hand instead of calling the serializer method. The one
  cross-check test (`test_vote_response_matches_topic_detail_poll_shape`)
  only asserts key-set equality plus 2 of the 6 fields
  (`total_votes`/`my_vote_option_id`) — `question`/`closes_at`/`is_closed`/
  `options` could silently diverge between `GET /topics/{id}/` and
  `POST .../poll/vote/` for the same poll and the test would still pass.
- **`_poll_payload()` re-queries for `my_vote_option_id` it already has.**
  `polls.py:111` — `post()` already holds the just-inserted vote's option
  in the local `option` variable a few lines earlier; the payload builder
  re-issues `PollVote.objects.filter(poll=poll, user=user).values_list(...)`
  instead of using `option.id` directly. One avoidable query per vote.
- **Client poll-option bounds are a hardcoded literal shadowing a
  configurable backend setting.** `web/src/pages/forum/NewThreadPage.tsx:27`
  — `MAX_POLL_OPTIONS = 10` / `MIN_POLL_OPTIONS = 2` mirror
  `WAGTAILFORUM_POLL_MAX_OPTIONS` / `POLL_MIN_OPTIONS`
  (`backend/packages/wagtail_forum/wagtail_forum/conf.py:131-133`) with only
  a code comment as the sync mechanism. Verified the defaults currently
  match (10/2 both sides) — dormant today, not a live bug — but
  `MIN_POLL_OPTIONS` directly gates `pollValid`/`canSubmit`: if an operator
  ever overrides either env var, the composer silently disagrees with the
  server (a lowered min can permanently block a poll size the server would
  accept; a raised max lets the client submit more options than the server
  now allows, 400ing the whole topic-create request after the user wrote a
  title and body).
- **A third hand-copied bounded-list serializer field.**
  `backend/packages/wagtail_forum/wagtail_forum/api/serializers.py:456` —
  `_BoundedOptionListField` repeats the exact "reject an oversized list
  before per-item validation" `to_internal_value` pattern already used by
  `_BoundedTagListField` and `_BoundedCandidateListField`, differing only
  in which constant it checks. The PR's own comment notes "same shape as
  `_BoundedTagListField`" but a third subclass was hand-written anyway
  instead of factoring one parameterized base.
- **Poll composer never exposes `closes_at`, so every poll is permanently
  open.** `web/src/pages/forum/NewThreadPage.tsx:466` — the model
  (`closes_at`), serializer (`TopicPollSerializer.closes_at`), README's
  documented request shape, and the frontend's own `CreatePollInput` type
  all support a close time; the composer only renders `question` and
  option inputs. Confirmed this was never a todo 309 acceptance criterion
  (its 4 ACs cover vote-rejection, server-computed results, Vitest
  coverage, and `spectacular`/`pytest` green only) — a real scope gap, not
  a violated requirement, and it means the backend's future-only
  `closes_at` validation and `PollCard`'s `is_closed` rendering are fully
  wired but unreachable from the only client that exists.
- **The poll/option consistency invariant lives only in one view, not the
  model or DB.** `backend/packages/wagtail_forum/wagtail_forum/models/polls.py:95`
  — a `PollVote`'s `option` must belong to its `poll`; this is enforced
  only by `PollVoteView.post`'s queryset filter (the model's own comment
  admits it). Verified today: `grep`ing the package for any `admin.py` or
  `wagtail_hooks.py` registering `Poll`/`PollOption`/`PollVote` finds
  nothing, so the Django-admin vector isn't currently reachable — the one
  view is genuinely the only extant write path. Still a defense-in-depth
  gap for any future writer (a data migration, a bulk tool, a second
  view) that wouldn't get the same protection for free.

## Recommended Action

1. Raw error envelope: either (a) have `apps/core/exceptions.py` format a
   nested `ValidationError`'s `detail` into a flat, readable string (walk
   the dict, join field:message pairs) instead of `str(exc)`, or (b) have
   the frontend's `authenticatedFetch` prefer a structured `errors` field
   over `message` when the backend supplies one, falling back to `message`
   only when it doesn't. Whichever direction, this is a shared-infra change
   — audit every page that renders `err.message` verbatim before shipping,
   not just the forum composer.
2. `PollCard` resync: add a `useEffect` that updates `current` when the
   `poll` PROP changes (not just on mount), guarded so it doesn't clobber a
   vote-in-flight or a more-recent locally-applied result — e.g. only
   resync when `pendingOptionId === null` and the incoming prop's data
   differs from `current`. Add a test that mounts `PollCard`, changes the
   `poll` prop (same `id`, different `vote_count`s), and asserts the
   displayed counts update.
3. Payload duplication: either have `PollVoteView` build its response by
   calling the same serializer method `TopicDetailSerializer.get_poll()`
   uses (same poll + requesting user), or strengthen
   `test_vote_response_matches_topic_detail_poll_shape` to assert full
   field-by-field equality against a real `TopicDetailSerializer` render,
   not just key-set plus two scalars.
4. Extra query: build `my_vote_option_id` in `_poll_payload()` from the
   already-known `option.id` instead of re-querying `PollVote`.
5. Client/server option-count drift: add a backend test that fails if
   `conf.py`'s `POLL_MIN_OPTIONS`/`POLL_MAX_OPTIONS` defaults ever diverge
   from the `MIN_POLL_OPTIONS`/`MAX_POLL_OPTIONS` TS constants (e.g. a
   Django management check or a fixture the frontend test suite reads),
   so a future config change is caught at review time instead of at
   400-time in production.
6. Bounded-list duplication: factor `_BoundedTagListField`,
   `_BoundedCandidateListField`, and `_BoundedOptionListField` into one
   parameterized base class (e.g. `_BoundedListField(max_items_setting,
   item_max_length_setting)`), each subclass reduced to a one-line
   settings reference.
7. `closes_at` UI: add a date/time (or "closes in N days") input to the
   poll composer in `NewThreadPage.tsx`, wired to `CreatePollInput.closes_at`;
   add a Vitest test asserting a submitted `closes_at` reaches the
   `createThread` call.
8. Poll/option invariant: add a `clean()` override (or a `save()` guard
   calling `full_clean()`) on `PollVote` that raises when
   `option.poll_id != poll_id`, so the same protection `PollVoteView`
   already provides exists for any future writer, not just this one view.

## Technical Details

- `backend/apps/core/exceptions.py` (custom DRF exception handler).
- `web/src/services/forumService.ts` (`authenticatedFetch`, `ForumApiError`).
- `web/src/components/forum/PollCard.tsx`, `PollCard.test.tsx`.
- `web/src/pages/forum/NewThreadPage.tsx` (one of several call sites that
  would benefit from item 1, not the only one — grep `err.message`/
  `error.message` across `web/src/pages/` and `web/src/components/` for the
  full blast radius before scoping the fix; also the composer to extend for
  item 7's `closes_at` input).
- `backend/packages/wagtail_forum/wagtail_forum/api/polls.py`
  (`PollVoteView._poll_payload()`, items 3–4).
- `backend/packages/wagtail_forum/wagtail_forum/api/serializers.py`
  (`_BoundedOptionListField` / `_BoundedTagListField` /
  `_BoundedCandidateListField`, item 6).
- `backend/packages/wagtail_forum/wagtail_forum/conf.py`
  (`POLL_MIN_OPTIONS`/`POLL_MAX_OPTIONS`, item 5).
- `backend/packages/wagtail_forum/wagtail_forum/models/polls.py`
  (`PollVote`, item 8).

## Acceptance Criteria

- [ ] A nested-serializer validation error (poll or otherwise) renders a
      readable message to the user, not a raw Python dict repr — test
      asserting the rendered text contains no `ErrorDetail`/`{'...':` markup
- [ ] `PollCard` reflects an updated `poll` prop on a same-thread refresh
      without losing an in-flight vote's optimistic-safe state — test
      asserting displayed counts change when the prop changes
- [ ] `test_vote_response_matches_topic_detail_poll_shape` asserts
      field-by-field equality across all 6 fields (or the vote response is
      derived from the same serializer method), not just key-set plus two
      scalars
- [ ] `_poll_payload()` no longer issues a second query for
      `my_vote_option_id` when the option is already known from the vote
      just recorded
- [ ] A test fails if the client's `MIN_POLL_OPTIONS`/`MAX_POLL_OPTIONS`
      diverge from the backend's `POLL_MIN_OPTIONS`/`POLL_MAX_OPTIONS`
      defaults
- [ ] `_BoundedTagListField`, `_BoundedCandidateListField`, and
      `_BoundedOptionListField` share one base class; existing tests for
      all three still pass unmodified
- [ ] The poll composer accepts an optional close time and it reaches the
      create-thread request — test asserting a submitted `closes_at` value
      is included in the API call
- [ ] `PollVote.full_clean()` (or equivalent) rejects an option that
      doesn't belong to its poll — test constructing a mismatched
      poll/option pair and asserting it raises

## Notes

p3. None of the eight findings are a live vulnerability or
data-corruption risk in a currently-reachable path (verified per-finding
above: config defaults match today, no admin.py exposes the poll models,
`closes_at` UI was never an AC). All are UX polish, latent
config/duplication drift, or defense-in-depth hardening. Deferred out of
todo 309 / PR #589 per this project's review-round discipline (fix
BLOCKING findings in round 1, non-blocking findings become a follow-up
todo rather than a third review round). See todo 309's Work Log for the
pre-merge review context (findings 1–2); findings 3–8 came from
`/code-review medium PR #589`, run post-merge-request against the pushed
branch.
