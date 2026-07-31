---
status: completed
priority: p3
issue_id: "285"
tags: [backend, forum, notifications]
dependencies: []
---

# Forum unread: seed `read_watermark_at` from a stable per-user fact, not first-touch wall clock

## Problem

Re-scoped out of todo 271 #1 (2026-07-29). `ForumProfile.read_watermark_at`
defaults to `timezone.now` at row-creation time, and `ForumProfile.for_user()`
— the lazy creation entry point — is reached from four non-test call sites,
only one of which means "this user read something":

| Call site | Is it a read? |
|---|---|
| `wagtail_forum/api/views.py` `TopicDetailView.retrieve` | yes |
| `wagtail_forum/api/views.py` `MeProfileView.get_object` | no — fetching own profile |
| `wagtail_forum/workflow.py` (x2) | no — trust check when submitting a post |
| `apps/forum_host/tasks.py` | no — **a third party's** push delivery |

For a pre-ship "sleeper" account (no profile row yet), whichever fires first
stamps `read_watermark_at = now()` and collapses that user's whole
pre-existing unread backlog forest-wide. Todo 271 accepted this as a
documented tradeoff (see the field comment in
`wagtail_forum/models/profiles.py`) — this todo tracks the actual fix.

## Recommended Action

Seed the initial watermark from a stable per-user fact instead of
wall-clock-at-first-touch, so *which* trigger creates the row stops mattering:

```python
joined = getattr(user, "date_joined", None)
defaults = {"read_watermark_at": joined} if joined else {}
profile, _ = cls.objects.get_or_create(user=user, defaults=defaults)
```

`getattr` with a fallback keeps this host-agnostic — `date_joined` is
`AbstractUser`-only, not part of the `AbstractBaseUser` contract the package
assumes, so a host without it falls back to today's exact behavior. Effects:

- **Sleeper account** — `date_joined` predates launch, so `Coalesce(TopicRead,
  watermark, UNREAD_LAUNCH_AT)` resolves to a pre-launch watermark and they
  correctly see their real backlog (there is no pre-launch forum content, so
  the flood stays bounded by launch either way).
- **Genuinely new signup** — `date_joined ≈ now`, i.e. unchanged from today.

Decide explicitly whether existing rows get a data migration or are left
alone; leaving them alone is defensible (migration 0016 already backfilled
them to a sane value).

## Technical Details

- `backend/packages/wagtail_forum/wagtail_forum/models/profiles.py` —
  `read_watermark_at` field + `ForumProfile.for_user()`.
- `backend/packages/wagtail_forum/wagtail_forum/api/views.py` —
  `_annotate_topic_unread` is the only consumer of the watermark.
- **Test wrinkle to fix while here**: `tests/test_profiles.py::
  test_for_user_stamps_read_watermark_at_creation_time` asserts
  `before <= profile.read_watermark_at <= after` around a
  `User.objects.create_user(...)` call. `create_user` sets `date_joined` to
  now, *inside* that window — so the test would keep passing under the change
  above while no longer testing what its name says. Rewrite it to create the
  user with an explicit backdated `date_joined` and assert the watermark
  tracks that, plus a case for a user object with no `date_joined` at all.

## Acceptance Criteria

- [x] `for_user()` seeds `read_watermark_at` from `date_joined` when the host
      user model exposes it, falling back to today's behavior when it doesn't
- [x] `test_for_user_stamps_read_watermark_at_creation_time` rewritten so it
      fails if the derivation regresses (backdated `date_joined`, not a
      coincidentally-in-window `now`)
- [x] A test covering a user model without `date_joined` (fallback path)
- [x] An explicit decision recorded on existing rows: data migration or leave
- [x] `wagtail_forum/models/profiles.py`'s todo-271 acceptance comment updated
      to reflect that the gap is now closed

## Work Log

### 2026-07-31 - Started by completing-todos skill (run 2026-07-31-0411)

- Picked up by automated workflow.

### 2026-07-31 - Implemented and verified

**Scope correction found while reading the code.** The todo's table lists four
`for_user()` call sites, but the standing comment in `profiles.py` already
recorded a fifth creation path the todo body did not carry into its Recommended
Action: `signals.py::_refresh_profile` calls
`ForumProfile.objects.get_or_create(user_id=author_id)` directly on every
post-count/trust recount, bypassing `for_user()` entirely. Fixing only
`for_user()` would have left that path stamping `now()`, so AC 5 ("the gap is
now closed") could not have been honestly checked. **Both** creation paths are
seeded.

Implementation:

- `ForumProfile.initial_read_watermark(user)` — `getattr(user, "date_joined",
  None) or timezone.now()`. Host-agnostic per the package rule: `date_joined`
  is `AbstractUser`-only, so a host without it falls back to pre-285 behaviour.
- `ForumProfile.initial_read_watermark_for_user_id(user_id)` — same seed for
  the signal handler, which holds only an id.
- Both are passed as **callables** in `get_or_create(defaults=...)`. Verified
  against the installed Django (`venv/.../db/models/query.py:993`,
  `params = dict(resolve_callables(params))`) that defaults are resolved
  *inside* the `except self.model.DoesNotExist` branch — so the extra user
  SELECT only runs when a row is actually created, never on the common
  already-exists path. Pinned by
  `test_signals_profile_creation_does_not_query_user_when_row_exists`.

**Decision on existing rows (AC 4): leave them alone, no data migration.**
Migration 0016 already backfilled every pre-existing row to migration-apply
time. Re-deriving those from `date_joined` would resurface an established
member's entire pre-0016 backlog as unread — precisely the flood 0016 was
written to prevent. The fix targets rows created *after* 0016, which is where
the trigger-order bug actually lives. Recorded in the field comment too.

Verification:

```
$ pytest packages/wagtail_forum/wagtail_forum/tests/test_profiles.py --reuse-db -q
packages/wagtail_forum/wagtail_forum/tests/test_profiles.py ........  [100%]
8 passed, 1 warning in 41.00s
```

Mutation check — the AC 2 requirement is that the test *fails* if the
derivation regresses, so the derivation was temporarily reverted to bare
`timezone.now()` and the suite re-run:

```
FAILED ...test_profiles.py::test_for_user_seeds_read_watermark_from_date_joined
FAILED ...test_profiles.py::test_signals_profile_creation_also_seeds_from_date_joined
2 failed, 6 passed
```

Both derivation tests go red under the mutant (the old test would have stayed
green). Source restored and re-verified before proceeding.

Full forum suite, fresh DB (page-creating suites need `--create-db`):

```
$ pytest packages/wagtail_forum apps/forum_host --create-db -q
620 passed, 2 warnings in 98.69s (0:01:38)
```

No unread-annotation test shifted, which was the risk: seeding from
`date_joined` moves a fixture user's watermark *earlier* (user creation) than
the old first-touch stamp (after topic setup), so an unread expectation could
have flipped. It did not.

### 2026-07-31 - Completed by completing-todos skill (run 2026-07-31-0411)

- Verification: all 5 acceptance criteria passed, each backed by quoted output
  above; both derivation tests mutation-proven to go red on regression.
- Review: 3 reviewers (django-drf, cross-cutting, wagtail). 1 high + 1 medium
  were the SAME finding from two reviewers — the query-count test hand-rolled
  its own `get_or_create` instead of calling `_refresh_profile`, so it could not
  fail on the regression it was named for. Repaired: the test now drives
  `_refresh_profile` itself and asserts on user-table queries, plus a
  create-path counterpart so the assertion is not vacuous. Mutation-verified
  (eager seed → red). 2 low comment-accuracy findings also repaired
  ("five modules" → four; the field-default reachability claim).

### 2026-07-29 - Created

- Re-scoped out of todo 271 #1 rather than bundled into it: todo 271 is a p3
  doc-closure item and this changes unread semantics for every existing
  account, which wants its own diff and its own review.

## Notes

p3 — no live user complaint behind it; the symptom is cosmetic (badge state)
and bounded to accounts predating their own profile row. Related: todo 271
(origin), todo 253 slice 5 / audit H10 (the unread feature itself).
