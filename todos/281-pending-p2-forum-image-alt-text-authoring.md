---
status: pending
priority: p2
issue_id: "281"
tags: [forum, a11y, web, drf, wagtail]
dependencies: []
source_review: "docs/audits/2026-07-11-forum-modernization.md"
source_finding: "M7"
---

# Forum: author-supplied image alt text, end to end (M7)

## Problem

A photo-centric plant community ships inline post images with **no
author-supplied alt text anywhere in the chain**. Every image a member posts
reaches a screen reader as its upload filename (`IMG_2481.jpg`) — filename-as-alt
is an accessibility anti-pattern, not a cosmetic gap. Promoted out of the todo
263 parking epic at the 2026-07-26 roadmap review as that epic's highest-value
member finding.

## Findings

Path shorthand: `W` = `backend/packages/wagtail_forum/wagtail_forum`, `web` = `web/src`.

State verified against `main` at 2026-07-26 (commit 27ade0c):

- **Upload stores the filename as the image's identity** —
  `PostImageUploadView.post` creates the row with
  `title=(image_file.name or "forum-image")[:255]` and no alt/description
  (`W/api/views.py:912-917`). No `alt` field is accepted on the multipart
  request (`W/api/views.py:874`, the `extend_schema` request body).
- **The serializer re-derives alt from that filename** —
  `serialize_image_for_api` returns `"alt": image.title or ""`
  (`W/api/serializers.py:268`), so the API's alt IS the filename.
- **The composer's alt is display-only and intentionally dropped on write** —
  `htmlToBodyBlocks` keeps only the wagtail image id (`web/utils/forumBody.ts:23-46`,
  documented at lines 17-22); `bodyBlocksToHtml` reads `alt` back out for display
  (`web/utils/forumBody.ts:58-60`); the TipTap insert seeds `alt: image.alt`
  from the upload response (`web/components/forum/TipTapEditor.tsx:119`).
- **Nothing prompts the author for alt text** — no alt input exists in the
  composer image flow (`TipTapEditor.tsx:99-128`).

Net: the alt round-trip is *structurally complete* — the one thing missing is a
human-authored value entering it. Nothing needs to be undone; a value needs to
be captured and stored.

## Proposed Solutions

### Option 1: store alt on the image row via `Image.description` (Recommended)

- **Implementation:** the composer collects alt text when inserting an image and
  sends it as an optional `alt` part on the existing multipart upload; the view
  writes it to `description`; `serialize_image_for_api` returns
  `image.description or ""` instead of `image.title`.
- **Pros:** `description` is Wagtail's own alt-text field, present in the pinned
  wagtail 7.4.2 (`wagtail/images/models.py:267`, `CharField(blank=True,
  max_length=255, default="")`, migration `images/0027_image_description`) — no
  project migration needed. Non-breaking: the `image` block value stays an `int`,
  so stored bodies, revisions, `build_forum_image_map`, `validate_forum_body`,
  and the mobile client are all untouched. `title` keeps its Wagtail-admin
  identification role.
- **Cons:** alt is per-image, not per-usage — re-embedding the same upload in a
  second post reuses the first post's alt. Acceptable for a forum (uploads are
  effectively single-use); note it in the package README.
- **Effort:** ~3-4 hours including tests.
- **Risk:** low — additive request field, one serializer line, no data migration.

### Option 2: promote the `image` block to a StructBlock `{image, alt}`

- **Implementation:** `ForumBodyBlock.image` becomes a `StructBlock`; per-usage
  alt travels in the body.
- **Pros:** correct per-usage semantics.
- **Cons:** breaking StreamField data change — every stored `Post.body` raw value
  flips `int` → `dict`, requiring a data migration across posts *and* revisions,
  plus coordinated changes to `validate_forum_body`'s `image_types`/`struct_types`
  branches (`W/api/sanitize.py:80-114`), `build_forum_image_map`'s
  `isinstance(raw["value"], int)` collector (`W/api/serializers.py:283-288`),
  `serialize_forum_body`, `htmlToBodyBlocks`, and the Flutter client.
- **Effort:** 1-2 days.
- **Risk:** high — a data migration over user content for a per-usage nicety.

## Recommended Action

1. **Backend — accept alt on upload.** In `PostImageUploadView.post`
   (`W/api/views.py:888`), read `request.data.get("alt")`, strip it, bound it to
   255 chars, and pass `description=<alt>` to `get_image_model().objects.create(...)`.
   Keep `title` as the (already sanitized) filename for admin identification.
   Add `alt` to the `extend_schema` multipart request properties so the OpenAPI
   contract stays complete (the todo-258 response-code work set that precedent).
   Note: `alt` participates in the idempotency fingerprint only via the existing
   content hash — decide explicitly whether a same-file/different-alt retry
   should replay (recommended: leave the fingerprint on content alone and
   document it, matching the M36 semantics already in the docstring).
2. **Backend — serve the authored value.** `serialize_image_for_api`
   (`W/api/serializers.py:254-272`): `"alt": image.description or ""`. Do NOT
   fall back to `title` — an empty alt is correct for a decorative image and is
   strictly better for a screen reader than a filename.
3. **Web — collect it.** In the `TipTapEditor` image flow
   (`web/components/forum/TipTapEditor.tsx:99-128`), prompt for alt text before
   or immediately after upload (reuse the link-editor popover shape at
   `applyLink`, which already models "collect a value, then apply"), pass it
   through `uploadPostImage` (`web/services/forumService.ts:302`), and keep
   seeding the inserted node's `alt` from the response. Empty alt must remain
   possible and must not block posting.
4. **Web — make it editable/visible.** Surface the current alt on a selected
   image (at minimum an "Edit alt text" affordance re-uploading is NOT required —
   the value can be PATCHed only if step 5 is taken; otherwise document the
   limitation in the composer hint text).
5. **Optional, decide during implementation:** a small authenticated
   `PATCH /post-images/{id}/` restricted to `uploaded_by_user == request.user`
   for alt corrections after insert. Skip if it grows the surface area beyond
   the a11y win.
6. **Docs.** Update the package README's API section and the alt-behavior note
   in `web/utils/forumBody.ts:17-22` (the "re-derived by the backend" comment
   stays true, but *what* it derives from changes).

## Technical Details

- Package purity: everything here lives inside `wagtail_forum` and the web
  client; no `apps.*` import is introduced, so `test_reusability.py` stays green.
- Sanitization: alt text is plain text by contract and must be HTML-escaped at
  render time like the other text blocks (`W/api/sanitize.py:1-12` states the
  convention). React escapes the `alt` attribute automatically; do not route it
  through `nh3`.
- Existing images: rows uploaded before this change have `description=""`, so
  their alt becomes `""` rather than the filename. That is the intended
  improvement, but call it out in the PR — it is a visible API value change for
  historic posts.
- Reference patterns: `backend/docs/patterns/security/file-upload.md` (the
  4-layer upload validation this rides on), `web/docs/patterns/react-typescript.md`.

## Acceptance Criteria

- [ ] `POST` to the post-image upload endpoint with an `alt` part stores it and
      returns it — asserted by a backend test that reads `Image.description`
      from the DB and the `alt` key from the response body
- [ ] Uploading with no `alt` part returns `alt: ""` (not the filename) —
      backend test asserts the filename does NOT appear in the serialized alt
- [ ] An over-long alt is bounded to 255 chars (or rejected with 400) rather
      than raising a `DataError` — backend test
- [ ] The composer sends author-entered alt text on upload — Vitest test on the
      image-insert flow asserting the value reaches `uploadPostImage`
- [ ] A rendered post image carries the authored alt — Vitest test on the post
      renderer
- [ ] `manage.py spectacular` passes with `alt` present in the upload request
      schema
- [ ] `pytest` forum suite and `npm run test` both green

## Work Log

### 2026-07-26 - Promoted out of todo 263 (roadmap review)

- Todo 263's own guidance ranked M7 first ("an accessibility gap, not polish").
  Findings above re-verified against `main` @ 27ade0c; line anchors refreshed
  from the 2026-07-11 audit's originals.
- Recorded Option 1 (`Image.description`) as recommended after confirming the
  field exists in the pinned wagtail 7.4.2 — this is the detail that makes the
  change non-breaking and was not known when the audit filed M7 as a "contract
  change".

## Notes

p2, not p3: an accessibility defect affecting every image in a photo-centric
community, with a low-risk fix now that `Image.description` is available.
Related: todo 276 (content-authoring remainder — M1/M5/M11/L8) touches the same
composer; sequence them to avoid TipTap toolbar conflicts.
