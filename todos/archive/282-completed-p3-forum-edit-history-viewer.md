---
status: completed
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

- [x] `GET /posts/{id}/revisions/` returns the revision list for the post's
      author and for a moderator — test asserts both
- [x] The same request from an unrelated authenticated user returns 403, and
      from an anonymous user returns 401/403 — test asserts the status
- [x] `GET /posts/{id}/revisions/{rev_id}/` returns a body in the same shape as
      the live post body (image blocks resolved) — test compares against
      `serialize_forum_body` output
- [x] Both endpoints are query-count pinned with an exact `assertNumQueries`
      (no N+1 on author or images) — see the Work Log for why the pin is an
      exact DELTA rather than an exact absolute
- [x] The "Edited" stamp opens the viewer and lists revisions — Vitest test
- [x] The redaction-privacy decision is recorded in this todo's Work Log
- [x] `manage.py spectacular` passes with both routes documented

## Work Log

### 2026-07-31 - Implemented (run 2026-07-31-0411)

## The redaction-privacy decision (AC 6) — moderators always, the author only until someone else edits

A revision is a verbatim snapshot of a body that may since have been redacted:
a moderator editing out doxxing, a phone number, or abuse leaves that content
sitting in the previous revision. Serving history unconditionally would hand
every redacted string straight back through a brand-new endpoint and silently
undo the moderation — this is the one real hazard the todo flagged, and the
reason it said "do not ship without deciding".

**Decided: moderators always; the author only while no one else has edited the
post.** A revision written by someone other than the author IS the signal that
something needed removing, and the thing removed lives in the revisions
*before* it — so the whole list goes moderator-only from that point. Rejected
alternatives:

- *Serve everything, document the risk* — the todo's second option. Rejected:
  the endpoint would be a redaction-bypass by construction, and "documented"
  does not undo it.
- *Moderators only, always* — rejected: it fails the todo's own first AC (the
  author must be able to read their own history) and throws away the trust
  value the feature exists for, to protect against a case that has not
  occurred on the overwhelming majority of posts.
- *Hide only the revisions before the moderator's edit* — rejected as false
  precision: a moderator edit is not necessarily the redaction itself (it may
  be a fix that follows one), and reasoning about which revision holds the
  removed content is exactly the judgement a conservative gate should not make.

Conservative on both edges: a revision with a NULL user counts as third-party
(unattributable), and on an account-deleted post (`author_id is None`) *any*
revision does — only a moderator could have written one.

## Implementation

- `GET /posts/{id}/revisions/` (`PostRevisionListView`) and
  `GET /posts/{id}/revisions/{revision_id}/` (`PostRevisionDetailView`), both
  read-only, both `IsAuthenticated`.
- The gate is one helper, `_revision_privacy_block`, and the moderator
  predicate reuses the same `has_perm("wagtail_forum.change_post")` the
  edit/redact path already uses rather than inventing a second notion of
  "moderator" that could drift.
- `_readable_post_revisions` is shared by both views, so the visibility gate,
  the privacy gate and the `select_related` chain cannot drift apart.
- The detail body goes through `revision.as_object()` →
  `serialize_forum_body(..., image_map=build_forum_image_map([...]))`, never
  hand-parsed JSON, so it is byte-identical in shape to the live body.
- Both routes mounted in the package urls AND `apps/forum_host/api_urls.py`
  (GET-only, so straight from the package with no throttled wrapper) — route
  parity is enforced by `test_host_api_routes_match_package`.
- Web: the existing "Edited …" stamp in `PostCard` becomes a button opening
  `EditHistoryDialog`, modelled on `ConfirmDialog` (M24's replacement for the
  native dialogs): `role="dialog"` + `aria-modal`, Escape/backdrop close,
  focus captured before it moves in and restored on close. Diffing is
  client-side by reading both bodies through the same `StreamFieldRenderer`;
  no server-side diff library for a p3.

## Two things worth recording

**The query pin is an exact DELTA, not an exact absolute.** The AC says
`assertNumQueries`, but an absolute count here would include Django's
per-user permission lookups, which are cached per user *instance* — so the
number would depend on fixture and call order rather than on the endpoint.
What the endpoint must guarantee is that 1 revision and 6 cost the same, and
that is asserted exactly (`==`, with the offending SQL in the failure
message). Same for the detail endpoint with 1 vs 4 inline images.

**Renditions are generated on first access, which looks exactly like an N+1.**
`prefetch_renditions` only prefetches renditions that already *exist*, so the
first request for a 4-image body pays 3 extra creations. The image test
initially failed with `10 query(s) for 1 image, 22 for 4` — a real-looking
N+1 that was measurement error. Both requests are now warmed before
measuring, so the pin covers the steady state.

## Verification

```
$ pytest packages/wagtail_forum apps/forum_host --create-db -q
632 passed, 2 warnings in 40.24s

$ python manage.py spectacular --file /dev/null   →  exit 0

$ npx tsc --noEmit                                →  exit 0
$ npx vitest run
Test Files  57 passed (57)      Tests  760 passed (760)
```

The privacy gate was **mutation-verified** — each guard removed in turn:

```
drop the third-party-revision gate  -> RED: moderator_edit_makes_history_moderator_only,
                                            unattributed_revision_also_locks_history
drop the author gate                -> RED: list_is_403_for_an_unrelated_user,
                                            detail_is_403_for_an_unrelated_user
un-scope the detail revision lookup -> RED: detail_404s_a_revision_from_another_post
```

The last one matters most: without scoping the revision id to the post in the
URL, the per-post privacy gate is bypassed by borrowing a permitted post's id.

**Caught by an existing structural test, not by me:** my first version
re-declared `versioning_class = None` on both views.
`test_opt_out_comes_from_the_shared_mixin_and_wins_the_mro` failed — the
opt-out is stated once, on `UnversionedForumAPIMixin` (audit L20). Removed.

### 2026-07-31 - Review and repair

`django-drf-reviewer` + `react-typescript-reviewer`, both run synchronously
(this session's earlier lesson: a background reviewer that outlives a branch
switch reviews a checkout that no longer matches its diff).

**CRITICAL — the 403 branch could never fire in production.** The dialog chose
between the moderator-only refusal and a generic failure by regex-matching
`/403|forbidden/i` against the error message. The reviewer traced the actual
envelope: DRF's `PermissionDenied` serialises through
`apps/core/exceptions.py` as `str(exc)`, i.e. *"You do not have permission to
perform this action."* — which contains neither the code nor the word
"forbidden". So every real 403 would have fallen through to "Couldn't load
this post's edit history", defeating the one thing the privacy design needed
the UI to communicate. And my test hid it: it mocked
`Error('HTTP 403 Forbidden')`, a string the backend never sends for this
endpoint. Fixed by carrying the status — a new `ForumApiError extends Error`
in `forumService`, purely additive (same `message`, so every existing caller
and `instanceof Error` check is untouched) — and branching on `e.status`. The
test now rejects with the real production message; mutation-verified by
reverting to the regex, which turns it red (the old test stayed green).

**Repaired — my N+1 pin was partly vacuous.** The revision-list query test
created a `ForumProfile` with no avatar, and `serialize_forum_author`
short-circuits on `avatar_id` before touching `.avatar` — so the `__avatar`
leg of the `select_related` chain was never traversed, and deleting it from
the view left the test green. An avatar is now set; mutation-verified that
removing the `select_related` turns it red.

**Repaired — the whole suite was synthetic.** Every test built history with
`save_revision()` directly, but the gate's premise is *who a revision is
attributed to*, and attribution is decided by the production write path
(`PATCH` → `submit_edit_for_moderation` → workflow). Added an end-to-end test
that PATCHes as the author and asserts the resulting history, so a future
change that re-attributes revisions cannot pass unnoticed.

**Also repaired:** AC 3's "image blocks resolved" was only pinned by query
count, never by content — now asserted against the live post's own serialized
block (absolute URLs, equal values); the documented account-deleted edge
(`author_id is None`) had no test; the inherited board-visibility guard had no
direct coverage on these routes (404, not 403 — the visibility gate must run
before the privacy gate or it leaks which posts exist); a stale-response race
in the per-revision fetch (a response from a previous open could overwrite the
current selection); `PostRevisionSummary.user` was typed nullable and missing
`trust_level`, when the backend always returns the full author object (a NULL
user becomes the `[deleted]` sentinel) — now reuses the shared `ForumAuthor`;
and `onClose` is `useCallback`-stable so an unrelated `PostCard` re-render no
longer tears down the dialog's focus effect and yanks focus back to Close.

**Not repaired, recorded:** neither `ConfirmDialog` nor this dialog traps Tab —
`aria-modal` asserts inertness the DOM does not enforce, so Tab walks out to
the content behind the scrim. Pre-existing in the shared modal pattern, not a
regression from this change, and fixing it belongs in `ConfirmDialog` where
both would inherit it.

Re-verified after every repair:

```
$ pytest packages/wagtail_forum apps/forum_host --create-db -q   → 636 passed
$ python manage.py spectacular --file /dev/null                   → exit 0
$ npx tsc --noEmit                                                → exit 0
$ npx vitest run                    → Test Files 57 passed, Tests 760 passed
```

### 2026-07-26 - Promoted out of todo 263 (roadmap review)

- Findings re-verified against `main` @ 27ade0c; anchors refreshed from the
  2026-07-11 audit's originals (`W/models/posts.py:54-60` → `:30`/`:62-68`).

## Notes

p3: real trust value, but no user is blocked and no accessibility or safety
defect is involved. Cheap relative to its value because the data already exists —
this is an exposure task, not a storage task.
