---
status: completed
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

- [x] `seed_default_forum` creates/ensures the forum image collection (idempotent;
      a test asserts running it twice yields exactly one collection).
- [x] `collections.py` get-or-create remains as the lazy fallback (unchanged
      behavior when the collection already exists).

## Notes

Root cause + reasoning recorded in `docs/LEARNINGS.md` (2026-06-25, "kimi-review
WARNINGs on the merged PR-3 backend").

## Work Log

### 2026-07-04 - Started by completing-todos skill (run 2026-07-04-0200)

- Picked up by automated workflow.

### 2026-07-04 - Implemented (run 2026-07-04-0200)

- `apps/forum_host/management/commands/seed_default_forum.py`: import + call
  `get_forum_image_collection()` at the end of `handle()` (deploy-time,
  single-threaded, so the request-time lazy get-or-create never races
  duplicates). Idempotent; help text updated to mention the collection.
- `collections.py` left untouched — the lazy get-or-create stays as the
  self-healing fallback for hosts that skip the seed.
- Test `apps/forum_host/tests/test_seed_command.py`:
  `test_seed_default_forum_creates_single_image_collection` runs the command
  twice and asserts `Collection.objects.filter(name="Forum Images").count() == 1`.

Verification:
- `pytest apps/forum_host/tests/test_seed_command.py
  packages/wagtail_forum/wagtail_forum/tests/test_collections.py` → **3 passed**.
- Regression: `pytest packages/wagtail_forum/ apps/forum_host/` → **165 passed**
  (164 + 1 new; the shared seed command's new step broke nothing).

### 2026-07-04 - Completed by completing-todos skill (run 2026-07-04-0200)

- Verification: both acceptance criteria passed (3 targeted tests + 165 full
  forum suite, quoted above).
- Review: `code-review-orchestrator` returned 0 blocking findings. 2 accepted
  (below-block-threshold):
  - MEDIUM — `get_forum_image_collection()` assumes `Collection.get_first_root_
    node()` is non-None. Accepted: it lives in `collections.py`, which AC2
    requires be left unchanged, and shipped pre-existing in PR-3a. The path is
    unreachable at deploy time — the root Collection is created by the same
    wagtailcore migrations as the root Page, and the command already guards
    `root Page is None → CommandError` (a strictly stronger precondition).
  - LOW — no test for the no-root-page `CommandError`. Accepted: exercises
    pre-existing command behavior the change didn't touch (out of scope).
