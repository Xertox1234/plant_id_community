---
status: pending
priority: p3
issue_id: "247"
tags: [forum, wagtail, concurrency, deployment]
dependencies: []
source_review: "kimi-review (codify pass on forum-spec2-pr3, 2026-06-25)"
source_finding: "WARNING: get_forum_image_collection non-atomic"
---

# Make the forum image collection deploy-time seeded (kill the get-or-create race)

## Problem

`get_forum_image_collection()` (`backend/packages/wagtail_forum/wagtail_forum/collections.py`)
does query-then-`add_child` lazily on first use. It is **not atomic**: two truly
concurrent *first-ever* image operations (an upload + a body validation, before
the collection exists) could each create a `"Forum Images"` collection. After
that, membership checks resolve `.first()` to one of them and reject images that
landed in the other.

Flagged by kimi-review (codify pass, 2026-06-25). Low risk — it's a one-time
startup race at the very first forum image ever; once the collection exists there
is no further race. Shipped as-is in PR-3a (#406).

## Recommended Action

Create the collection at **deploy time**, where it runs single-threaded, so the
request-time get-or-create always finds it and never races:

- Add `get_forum_image_collection()` to the `seed_default_forum` management
  command (already in the Railway `startCommand`, and idempotent). The lazy
  get-or-create in `collections.py` stays as a self-healing fallback for hosts
  that don't run the seed.

Alternative (heavier): a `get_or_create`-style helper with a savepoint + retry,
or a unique constraint on `(parent, name)` — but treebeard `add_child` makes the
deploy-time seed the simplest robust fix.

## Acceptance Criteria

- [ ] `seed_default_forum` creates/ensures the forum image collection (idempotent;
      a test asserts running it twice yields exactly one collection).
- [ ] `collections.py` get-or-create remains as the lazy fallback (unchanged
      behavior when the collection already exists).

## Notes

Root cause + reasoning recorded in `docs/LEARNINGS.md` (2026-06-25, "kimi-review
WARNINGs on the merged PR-3 backend").
