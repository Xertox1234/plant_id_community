---
status: pending
priority: p3
issue_id: "282"
tags: [forum, drf, web, moderation]
dependencies: []
source_review: "docs/audits/2026-07-11-forum-modernization.md"
source_finding: "M4"
---

# Forum: expose post edit history (M4)

## Problem

Every forum post edit is already persisted as a Wagtail revision, and the web UI
already stamps `Edited <time> by <user>` on the post — but there is no endpoint
and no viewer behind that stamp. The data exists and is being paid for
(revision rows on every edit) while delivering none of its trust value: a reader
cannot see *what* changed, and a moderator cannot audit an edit without the
Wagtail admin. Promoted out of the todo 263 parking epic at the 2026-07-26
roadmap review.

## Findings

Path shorthand: `W` = `backend/packages/wagtail_forum/wagtail_forum`, `web` = `web/src`.

State verified against `main` at 2026-07-26 (commit 27ade0c):

- **Revisions are stored.** `Post` mixes in `RevisionMixin` (`W/models/posts.py:30`)
  with a canonical `revisions` `GenericRelation` overriding the mixin's property
  (`W/models/posts.py:62-68`). `save_revision` runs on the edit/moderation path
  (`W/workflow.py:110`, `:137`, `:204`).
- **The stamp exists, with nothing behind it.** `PostCard` renders
  `Edited <Timestamp> by <name>` from `edited_at`/`edited_by`
  (`web/components/forum/PostCard.tsx:153-159`) — text only, not a link.
- **No revision endpoint.** No route in `W/api/urls.py` serves revisions; the
  only way to read one today is the Wagtail admin.

## Recommended Action

1. **Read-only list endpoint.** `GET /posts/{id}/revisions/` returning
   `[{id, created_at, user: <PostAuthorSerializer shape>}]`, newest first.
   Reuse the existing author serializer so the identity shape stays consistent
   with the rest of the API (todo 257's H26 convention — including the
   deleted-author convention from M41).
2. **Permission gate.** Author + moderators only. The ViewSet/APIView must call
   `super().get_permissions()` if it uses `@action` (Critical Gotcha #1 —
   enforced by `docs/rules/triggers.json`); mirror the existing moderator check
   used by the edit/redact endpoints rather than inventing a new one.
3. **Detail/diff endpoint.** `GET /posts/{id}/revisions/{rev_id}/` returning
   that revision's serialized body through `serialize_forum_body` so the shape
   matches the live post exactly. Render the diff client-side; do not add a
   server-side diff library for a p3.
4. **Web viewer.** Make the existing "Edited" stamp a button opening a modal
   listing revisions, with a per-revision body view. Reuse the app's dialog
   pattern (M24 replaced native dialogs — follow that component).
5. **Privacy call, record it in the Work Log:** a redacted/moderated post's
   earlier revisions still contain the pre-redaction content. Either exclude
   revisions of redacted posts from the author-facing list (moderators only), or
   state explicitly why full history is acceptable. Do not ship without deciding
   — this is the finding's one real hazard.

## Technical Details

- Revision bodies are stored as serialized JSON of the object; deserialize via
  the revision's `as_object()` and feed `post.body` to `serialize_forum_body`
  (`W/api/serializers.py:298`) rather than hand-parsing the JSON.
- N+1 risk: the list endpoint must `select_related("user")` and the detail
  endpoint must build an image map (`build_forum_image_map`) for any image
  blocks, exactly as the post-list path does (`W/api/views.py:599-618`).
- Package purity: revisions are `wagtailcore` — no `apps.*` import needed, so
  `test_reusability.py` stays green.
- Patterns: `backend/docs/patterns/architecture/viewsets.md`,
  `backend/docs/patterns/domain/forum.md`.

## Acceptance Criteria

- [ ] `GET /posts/{id}/revisions/` returns the revision list for the post's
      author and for a moderator — test asserts both
- [ ] The same request from an unrelated authenticated user returns 403, and
      from an anonymous user returns 401/403 — test asserts the status
- [ ] `GET /posts/{id}/revisions/{rev_id}/` returns a body in the same shape as
      the live post body (image blocks resolved) — test compares against
      `serialize_forum_body` output
- [ ] Both endpoints are query-count pinned with an exact `assertNumQueries`
      (no N+1 on author or images)
- [ ] The "Edited" stamp opens the viewer and lists revisions — Vitest test
- [ ] The redaction-privacy decision is recorded in this todo's Work Log
- [ ] `manage.py spectacular` passes with both routes documented

## Work Log

### 2026-07-26 - Promoted out of todo 263 (roadmap review)

- Findings re-verified against `main` @ 27ade0c; anchors refreshed from the
  2026-07-11 audit's originals (`W/models/posts.py:54-60` → `:30`/`:62-68`).

## Notes

p3: real trust value, but no user is blocked and no accessibility or safety
defect is involved. Cheap relative to its value because the data already exists —
this is an exposure task, not a storage task.
