---
status: pending
priority: p4
issue_id: "338"
tags: [forum, wagtail, django, moderation]
dependencies: []
source_review: "docs/audits/2026-09-04-forum.md"
source_finding: "M1"
---

# Topic.author needs blank=True parity with Post.author for republish after author deletion

## Problem

`Topic.author` is `null=True, on_delete=SET_NULL` but not `blank=True`, unlike
`Post.author`. Wagtail's `save_revision()` runs `full_clean()`, which rejects a
NULL-but-not-blank FK — so a topic whose author account was deleted cannot be
taken through the "hide → fix slug → republish" moderation flow the audit M1
fix covers: `save_revision()` raises `ValidationError: {'author': ['This field
cannot be blank.']}`. `docs/LEARNINGS.md` 2026-07-03 recorded exactly this for
`Post.author`; `Topic.author` was never given the same treatment.

## Findings

- `backend/packages/wagtail_forum/wagtail_forum/models/topics.py:37-42` —
  `author` FK: `null=True`, `on_delete=models.SET_NULL`, no `blank=True`.
- `backend/packages/wagtail_forum/wagtail_forum/models/posts.py` — `Post.author`
  carries `blank=True` for this reason (LEARNINGS 2026-07-03).
- `backend/apps/forum_host/tests/test_topic_redirects.py::_published_topic` —
  the audit's own tests had to supply an author precisely because
  `save_revision()` fails without one (surfaced by the Phase 6 wagtail
  reviewer while tracing `full_clean()`).

## Recommended Action

1. Add `blank=True` to `Topic.author`; `makemigrations wagtail_forum` (a
   no-op DB migration — `blank` is validation-only, but Django still records
   it).
2. Test: create a published topic, delete its author (`SET_NULL`), then
   `topic.save_revision().publish()` succeeds; and the M1 flow
   (unpublish → rename → publish) still writes the redirect.
3. Confirm the admin snippet form does not now show "author" as optional in a
   way that lets a moderator blank it by hand (`FieldPanel` list at
   `topics.py:118-124` does not include `author`, so it should be unaffected).

## Technical Details

- `Post.author` precedent and the `full_clean()` trace: `docs/LEARNINGS.md`
  2026-07-03.
- The audit's `_published_topic` helper in `test_topic_redirects.py` shows the
  failure shape (`ValidationError` from `wagtail/models/revisions.py:408`).

## Acceptance Criteria

- [ ] `Topic.author` has `blank=True` and a migration is committed.
- [ ] A test republishes a topic with a deleted (NULL) author without error.
- [ ] `makemigrations --check` clean.

## Work Log

### 2026-09-04 - Filed from the forum audit's Phase 6 review

- Out-of-scope observation by the wagtail reviewer (`topics.py` untouched by
  the audit PR); filed per the review-loop budget.

## Notes

p4: only bites after an author account deletion, and only on the republish
path; moderators can still unpublish/delete such a topic.
