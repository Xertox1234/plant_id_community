---
status: pending
priority: p3
issue_id: "320"
tags: [forum, web, api]
dependencies: []
source_review: "todo 309 (deferred 2026-08-30)"
---

# Forum polls: two deferred review findings (raw error envelope, stale-poll resync)

## Problem

Two findings surfaced during `react-typescript-reviewer`'s review of todo
309 (forum polls) that were deliberately NOT fixed there — one because it's
a pre-existing, cross-cutting infra issue well outside a single feature's
surgical scope; the other because it's a narrow, non-corrupting edge case
where a rushed fix risked introducing a new bug.

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

## Technical Details

- `backend/apps/core/exceptions.py` (custom DRF exception handler).
- `web/src/services/forumService.ts` (`authenticatedFetch`, `ForumApiError`).
- `web/src/components/forum/PollCard.tsx`, `PollCard.test.tsx`.
- `web/src/pages/forum/NewThreadPage.tsx` (one of several call sites that
  would benefit from item 1, not the only one — grep `err.message`/
  `error.message` across `web/src/pages/` and `web/src/components/` for the
  full blast radius before scoping the fix).

## Acceptance Criteria

- [ ] A nested-serializer validation error (poll or otherwise) renders a
      readable message to the user, not a raw Python dict repr — test
      asserting the rendered text contains no `ErrorDetail`/`{'...':` markup
- [ ] `PollCard` reflects an updated `poll` prop on a same-thread refresh
      without losing an in-flight vote's optimistic-safe state — test
      asserting displayed counts change when the prop changes

## Notes

p3. Neither finding is a live vulnerability or data-corruption risk — both
are UX polish. Deferred out of todo 309 per this project's review-round
discipline (fix BLOCKING findings in round 1, non-blocking findings become
a follow-up todo rather than a third review round). See todo 309's Work
Log for the fuller review context both findings came from.
