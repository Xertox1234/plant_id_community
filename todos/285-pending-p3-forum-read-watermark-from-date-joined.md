---
status: pending
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

- [ ] `for_user()` seeds `read_watermark_at` from `date_joined` when the host
      user model exposes it, falling back to today's behavior when it doesn't
- [ ] `test_for_user_stamps_read_watermark_at_creation_time` rewritten so it
      fails if the derivation regresses (backdated `date_joined`, not a
      coincidentally-in-window `now`)
- [ ] A test covering a user model without `date_joined` (fallback path)
- [ ] An explicit decision recorded on existing rows: data migration or leave
- [ ] `wagtail_forum/models/profiles.py`'s todo-271 acceptance comment updated
      to reflect that the gap is now closed

## Work Log

### 2026-07-29 - Created

- Re-scoped out of todo 271 #1 rather than bundled into it: todo 271 is a p3
  doc-closure item and this changes unread semantics for every existing
  account, which wants its own diff and its own review.

## Notes

p3 — no live user complaint behind it; the symptom is cosmetic (badge state)
and bounded to accounts predating their own profile row. Related: todo 271
(origin), todo 253 slice 5 / audit H10 (the unread feature itself).
