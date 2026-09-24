---
status: completed
priority: p3
issue_id: "368"
tags: [forum, web, e2e, uploads]
dependencies: []
---

# Browser coverage for the forum image save → reopen round trip

## Problem

`web/e2e/forum-image-upload.spec.js` (todo 357) covers the composer half of the
inline-image path in a real browser: pick a file, reject a bad one, upload once
with an `Idempotency-Key`, insert a node carrying the server id, mark it
decorative via **Skip**, and re-author its alt text without re-uploading.

It stops at insert. It never **posts** the thread and never **reopens it for
edit**. So todo 357's AC 5 (*"new threads, replies, and edits serialize it as an
`image` body block"*) and AC 6 (*"editing an existing post rehydrates the image
and preserves its id; the rendered post uses the safe image URL and stored alt
text"*) are verified **in jsdom only** —
`web/src/utils/forumBody.test.ts:70,83` (`htmlToBodyBlocks` /
`bodyBlocksToHtml` round trip, one of them through a real TipTap editor),
`web/src/components/StreamFieldRenderer.test.tsx`, and the backend's
`test_post_list.py` / `test_post_edit_delete.py` — plus the migration's
zero-bare-PKs assertion.

## Findings

Todo 357 is the reason this is worth doing rather than assumed-fine. Its e2e
spec, on its very first execution, caught a defect that **every** jsdom test and
**every** Django-test-client test had passed straight through: the composer sent
an `Idempotency-Key` header that was not in `CORS_ALLOW_HEADERS`, so the browser
refused to send the upload POST at all (200 preflight, header omitted, no
request, nothing in the server log). Fixed in PR #705 (`e2fe42f`).

That is direct, same-feature evidence that "jsdom passes" and "the browser
works" are different claims on this path. The save → reopen leg is the part of
that path with no browser evidence.

## Recommended Action

Extend `web/e2e/forum-image-upload.spec.js` (do not add a second spec file — it
is already registered in seven places in `playwright.config.ts`) with one test:

1. Upload an image with authored alt text, type a title and body, submit the
   thread.
2. Assert the rendered post shows the image with the stored alt text and an
   absolute image URL.
3. Reopen the post for edit; assert the editor rehydrates an
   `img[data-image-id]` with the SAME server id, and that saving again without
   touching the image does not issue a second POST to `/forum/images/`.
4. Repeat step 3's id assertion for a **decorative** image, whose correct
   markup is `alt=""` + `data-decorative="true"` — a missing alt and an
   intentionally empty one must not be confused.

## Scope

- `web/e2e/forum-image-upload.spec.js` only.
- Keep the existing "count every POST to `/forum/images/`" discipline: a silent
  duplicate upload on edit is exactly the regression this leg would catch.
- Stay inside one Playwright project (`chromium-authenticated`). A full
  unfiltered run hits the Postgres exhaustion of todo 331, and login is
  IP-limited to 5/15m.

## Acceptance Criteria

- [x] A posted thread's rendered image is asserted in a real browser: correct
      `src`, correct stored alt text.
- [x] Reopening that post for edit rehydrates the image node with the same
      server id, asserted in a real browser.
- [x] A decorative image round-trips as `alt=""` + `data-decorative="true"`,
      not as a missing alt.
- [x] Editing and re-saving a post whose image is unchanged issues ZERO new
      requests to `/api/v1/forum/images/`.
- [x] `./node_modules/.bin/playwright test e2e/forum-image-upload.spec.js
      --project=chromium-authenticated` passes, run directly (RTK mangles
      Playwright filter args) with output quoted in the Work Log.

## Technical Details

- `web/e2e/forum-image-upload.spec.js`
- `web/src/utils/forumBody.ts` (`htmlToBodyBlocks` / `bodyBlocksToHtml`)
- `web/src/components/StreamFieldRenderer.tsx`
- `backend/packages/wagtail_forum/wagtail_forum/api/serializers.py`
  (`serialize_forum_body`, `build_forum_image_map`)

## Notes

p3, not p2: the round trip is genuinely covered by unit and backend tests, and
todo 357's PR #702 additionally proved the stored shape with a migration
assertion that ZERO bare image PKs remain in either `Post.body` or
`wagtailcore.Revision`. This is about closing the one leg where the evidence is
jsdom rather than a browser — worth doing precisely because that distinction has
already cost this feature once.

## Work Log

### 2026-09-07 - Filed while archiving todo 357

- Filed deliberately rather than silently checking todo 357's AC 5/6 as browser-
  verified. They are unit-verified; the browser leg stops at insert.
- Prompted by the CORS defect (PR #705) that todo 357's first e2e execution
  found, which no jsdom or Django-test-client test could have caught.

### 2026-09-24 - Done: save -> reopen round trip covered in a real browser

- Extended `web/e2e/forum-image-upload.spec.js` (no new spec file) with an
  `imageRoundTrip(page, { alt })` helper and two tests: authored alt, and
  decorative (Skip). Each posts a thread via the board picker, asserts the
  rendered opening post's `max-1200x1200` rendition `img` (stored alt, absolute
  `/media/images/` src, and `naturalWidth > 0` — the browser actually decoded
  it), reopens it for edit and asserts the rehydrated `img[data-image-id]`
  carries the SAME server id and alt (decorative: `alt=""` +
  `data-decorative="true"`; authored: no `data-decorative`), then replaces the
  text (image untouched) and saves.
- The re-save asserts the PATCH body's image blocks equal exactly
  `[{image: <same id>, alt_text, decorative}]` — so "zero new uploads" cannot
  pass by the image being silently dropped — then that the re-rendered post
  still shows it, and that exactly ONE POST to `/api/v1/forum/images/` was made
  across post + reopen + re-save (counted from the test's first line).
- Command (run directly, backend started from the worktree with
  `PYTHONPATH=backend/packages/wagtail_forum`):
  `./node_modules/.bin/playwright test e2e/forum-image-upload.spec.js --project=chromium-authenticated`

  ```
    ✓  1 [setup-chromium] › e2e/auth.setup.js:39:1 › authenticate as test user (2.8s)
    ✓  2 [chromium-authenticated] › e2e/forum-image-upload.spec.js:233:3 › Forum inline image upload › rejects an unsupported file client-side, announces it, and accepts a real image afterwards (3.7s)
    ✓  4 [chromium-authenticated] › e2e/forum-image-upload.spec.js:271:3 › Forum inline image upload › Skip stores the image as decorative, and alt can be re-authored afterwards without re-uploading (4.0s)
    ✓  5 [chromium-authenticated] › e2e/forum-image-upload.spec.js:309:3 › Forum inline image upload › the Insert image control has an accessible name and works at a mobile width (4.1s)
    ✓  6 [chromium-authenticated] › e2e/forum-image-upload.spec.js:176:3 › Forum inline image upload › uploads a chosen image in ONE authenticated multipart request and inserts a node carrying the server id (4.1s)
    ✓  3 [chromium-authenticated] › e2e/forum-image-upload.spec.js:346:3 › Forum inline image upload › a posted image renders with its stored alt, rehydrates with the same id on edit, and re-saves without re-uploading (5.7s)
    ✓  7 [chromium-authenticated] › e2e/forum-image-upload.spec.js:352:3 › Forum inline image upload › a decorative image round-trips as alt="" + data-decorative="true", not as a missing alt (3.0s)
    7 passed (10.7s)
  ```

- Mutation checks (each applied to a `cp` backup, restored with `cp`, restored
  line grep-verified):
  - `bodyBlocksToHtml` emits `data-image-id="${id}0"` -> both new tests fail at
    the rehydrated-id assertion (`Expected: "21" Received: "210"`); the four
    pre-existing tests still pass, so the mutation is targeted.
  - `bodyBlocksToHtml` never emits `data-decorative` -> only the decorative
    test fails, at `data-decorative` (`Expected: "true" Received: ""`). The
    PATCH assertion would NOT catch this one on its own — `imageBlockFrom`
    re-derives `decorative` from a blank alt — which is why the attribute
    assertion is there.
  - `StreamFieldRenderer` drops the `alt` prop -> both fail at the rendered
    alt; the decorative one reports `Expected: "" Received: serializes to the
    same string`, i.e. a MISSING alt is not accepted as an empty one.
- First run failed on the test itself, not the product: `End` is not a
  line-end key in a macOS Chromium contenteditable, so the appended text landed
  one character early. Replaced with a triple-click-and-retype of the text
  paragraph.
