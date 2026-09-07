---
status: completed
priority: p2
issue_id: "357"
tags: [forum, web, uploads, accessibility]
dependencies: []
---

# Wire up the forum image upload button end to end

## Problem

The forum composer exposes an **Insert image** control, but the complete upload
path needs to be treated as one verified feature: selecting a file, validating
it, collecting accessible alt text, uploading it through the forum API,
inserting the returned image into the TipTap document, and preserving that
image through thread creation, replies, edits, and rendering.

The current web code contains a partial image path (`TipTapEditor`,
`uploadPostImage`, and the forum image node). Audit that implementation first
and close only the missing integration or production-flow gaps; do not create a
second upload path.

## Findings

The partial implementation named in the Problem section is real, not assumed —
every reference below was resolved during the PR #688 review:

- `web/src/services/forumService.ts:571` —
  `export async function uploadPostImage(imageFile: File, alt?: string): Promise<UploadedImage>`
  already exists, and already takes an `alt` argument.
- `web/src/components/forum/TipTapEditor.tsx`,
  `web/src/components/forum/forumImageNode.ts`, `web/src/utils/forumBody.ts`,
  `web/src/components/StreamFieldRenderer.tsx`,
  `backend/packages/wagtail_forum/wagtail_forum/api/views.py` and
  `.../api/sanitize.py` all exist.

No audit of *behaviour* has been performed yet. Which of the Acceptance Criteria
below already hold, and which are genuinely missing, is unknown until the trace
in Scope is run — that is the first task, not a formality.

## Recommended Action

1. Run the Scope trace end to end and record, per Acceptance Criterion, whether
   it currently passes. This turns the criteria into a checklist with evidence
   rather than a wishlist.
2. Close only the gaps that trace surfaces. Do not add a second upload path
   alongside `uploadPostImage`.
3. Fill in the Findings section above with what the trace actually found before
   writing any code.

## Scope

- Trace the button → hidden file input → client validation → alt-text prompt →
  multipart upload → TipTap image node → `htmlToBodyBlocks` → API flow.
- Verify the backend upload endpoint enforces authentication, CSRF, ownership,
  collection membership, MIME/type, size, and image validation.
- Verify the returned image id survives create-thread, reply, and edit payloads
  and round-trips through `bodyBlocksToHtml` when editing a post.
- Verify the rendered forum post displays the uploaded image safely and with
  the stored alt text.

## Acceptance Criteria

- [x] Clicking or keyboard-activating **Insert image** opens the file picker;
      the control has an accessible name and works at mobile widths.
- [x] Unsupported MIME types and files over the configured size limit are
      rejected before upload, with an announced actionable error; selecting
      the same file again after an error works.
- [x] The author is prompted for alt text before upload; both authored alt text
      and an intentional empty/decorative alt value are handled correctly.
- [x] A valid image submits one authenticated multipart request to the forum
      image endpoint, shows a loading state, and reports upload failures without
      losing the draft.
- [x] A successful response inserts an image node carrying the server image id;
      new threads, replies, and edits serialize it as an `image` body block.
- [x] Editing an existing post rehydrates the image and preserves its id; the
      rendered post uses the safe image URL and stored alt text.
- [x] Add or update service, component, serialization round-trip, and browser
      coverage for the complete path; no test relies on a real external image
      service or committed credentials.
- [x] `npm run type-check`, `npm run lint`, focused tests, and the relevant
      browser flow pass.

## Technical Details

- `web/src/components/forum/TipTapEditor.tsx`
- `web/src/services/forumService.ts` (`uploadPostImage`)
- `web/src/components/forum/forumImageNode.ts`
- `web/src/utils/forumBody.ts`
- `backend/packages/wagtail_forum/wagtail_forum/api/views.py`
- `backend/packages/wagtail_forum/wagtail_forum/api/sanitize.py`
- `web/src/components/StreamFieldRenderer.tsx`

## Notes

p2 because this is a visible forum affordance and an incomplete or unreliable
upload path can cause user content loss, inaccessible images, or orphaned
uploads. The existing partial implementation must be verified before any new
code is added.

## Work Log

### 2026-09-06 - Filed and made template-compliant

- Filed by an earlier session; lived untracked in the working tree until
  committed in PR #688.
- Review of PR #688 found the file missing three sections required by
  `todos/TEMPLATE.md:12` (`Findings`, `Recommended Action`, `Work Log`) and
  naming `Technical Details` as `Technical References`. All four fixed here.
- The added `Findings` content is deliberately limited to references verified
  during that review (file existence, and `uploadPostImage` at
  `forumService.ts:571`). The behavioural audit this todo asks for has NOT been
  run, and no finding from it has been invented — that remains task 1.

### 2026-09-07 - Audited, implemented, and verified (PRs #702, #703, #704, #705)

**The premise was inverted.** Task 1 was "run the Scope trace and record, per
Acceptance Criterion, whether it currently passes." It did — almost all of it.
The feature already shipped end to end: button, hidden file input, client
MIME/size validation, pre-upload alt prompt, `aria-live` error region,
multipart upload, a TipTap node carrying the server id, `{type:'image'}`
serialization, 4-layer server validation, uploader + collection-membership
checks, ~20 backend tests and ~11 frontend tests.

The todo was filed on the strength of one **stale comment**,
`web/src/services/forumService.ts:4-6`: *"they are not wired into any compose
UI."* False since PR-3 — `uploadPostImage` was called from
`TipTapEditor.tsx:184` and `IdentifyPage.tsx:112`. PR #703 deletes the comment.
Audit the premise of a todo before building.

Two criteria genuinely failed (AC 4, AC 7) and one could not be settled by
reading (AC 8). Given that, the scope was widened by explicit decision to also
migrate `ImageChooserBlock` → `ImageBlock` and add paste/drag-drop.

#### Per-AC ledger

| AC | Verdict | Evidence | Verified where |
| --- | --- | --- | --- |
| 1 picker opens, accessible name, mobile widths | passed on `main` | `forum-image-upload.spec.js:187` at a 390px viewport; `ToolbarButton` mirrors `title` into `aria-label` (name-from-content never applies to a button whose only child is an aria-hidden icon) | **browser** |
| 2 MIME/size rejected pre-upload, announced, re-selectable | passed on `main` | `forum-image-upload.spec.js:111` — a PDF is refused with zero network calls and no alt prompt, then a real JPEG is accepted | **browser** |
| 3 alt prompt; authored + decorative both handled | passed on `main`, improved | `forum-image-upload.spec.js:54` (authored) and `:149` (Skip → `alt=""` + `data-decorative="true"`) | **browser** |
| 4 ONE authenticated multipart request, loading state, no draft loss | **FAILED on `main`; fixed in #703** | Insert-image button had no `disabled`; the frontend never sent `Idempotency-Key` though the backend's M36 replay path was fully built and inert. `forum-image-upload.spec.js:54` now asserts exactly one POST, `multipart/form-data`, a non-empty `idempotency-key`, and that typed text survives the insert | **browser** |
| 5 inserts node with server id; serializes as an `image` block | passed on `main`, shape changed | Node id asserted in the browser (`:97`). **Serialization** asserted in jsdom: `web/src/utils/forumBody.test.ts:70` and `:83` (the latter through a real TipTap editor) | insert **browser**, serialize **jsdom** |
| 6 edit rehydrates and preserves id; safe URL + stored alt | passed on `main`, shape changed | `web/src/utils/forumBody.test.ts:70,83`; `web/src/components/StreamFieldRenderer.test.tsx`; backend `tests/api/test_post_list.py`, `tests/api/test_post_edit_delete.py`; migration 0038 asserts ZERO bare image PKs remain in `Post.body` **or** `wagtailcore.Revision` | **jsdom + backend, not browser** |
| 7 service, component, round-trip **and browser** coverage | **FAILED on `main`; closed in #704** | No e2e spec existed and `data-testid="forum-image-input"` was unused by any spec. Browser coverage now spans picker → validation → alt prompt → upload → insert → alt re-edit. It stops before save → reopen (see todo 368) | mixed |
| 8 type-check, lint, focused tests, browser flow | **unverified until run** | Run first-hand on merged `main`, not only cited from CI: `npm run type-check` exit 0; `npm run lint` exit 0 (1 warning, in a generated `coverage/` artifact); focused vitest `Test Files 5 passed (5) / Tests 205 passed (205)`. CI green on #702 (17/17), #704 (17/17), #703 (5/5 required; CodeQL is a pre-existing false positive, below). The browser flow is the run quoted below | **browser** |

#### The browser flow, first execution

The spec had never been executed — only authored and discovery-verified. Its
first run was **red**, and it caught a real defect (next section). After PR #705:

```
✓ the Insert image control has an accessible name and works at a mobile width (3.0s)
✓ rejects an unsupported file client-side, announces it, and accepts a real image afterwards (3.3s)
✓ Skip stores the image as decorative, and alt can be re-authored afterwards without re-uploading (3.4s)
✓ uploads a chosen image in ONE authenticated multipart request and inserts a node carrying the server id (3.7s)

5 passed (9.8s)
```

#### What the first e2e run found: a CORS regression #703 introduced

Three of four tests timed out on `waitForResponse`. The Django log showed **3
`OPTIONS /api/v1/forum/images/` and zero `POST`s**: the browser sent the
preflight and then declined to send the request.

`Idempotency-Key`, newly sent by #703, was not in `CORS_ALLOW_HEADERS`. CORS is
an allowlist that fails silently — the preflight still returns **200**, the
response simply omits the header, the browser never sends the real request, so
Django logs nothing, and `CORS_PREFLIGHT_MAX_AGE` caches the refusal for 24h.
Confirmed by curl against the live production API too: for
`Origin: https://houseplant-md.com`, `access-control-allow-headers` omitted it.

Nothing else could have caught it. The backend had honoured the header since
M35, but only the Flutter app ever sent one and a native client is not subject
to CORS; jsdom does not enforce CORS; the Django test client does not either;
and there was no test of `CORS_ALLOW_HEADERS` anywhere in the repo. Fixed in
**PR #705** `e2fe42f` with a real-preflight regression test
(`apps/forum_host/tests/test_cors_preflight.py`, verified by mutation) and rules
in `docs/rules/api.md` + `docs/rules/typescript.md`, which route to
`settings.py` and `web/src/services/*.ts` respectively.

**Deploy ordering (action for the operator):** the backend fix must be live on
Railway *before or with* the frontend build that sends the header.
`Workers Builds: plantidcommunity` runs as a per-PR check, so the web app
deploys from `main` on its own. Whether the #703 bundle has already shipped
could not be confirmed either way — a grep of the eight chunks reachable from
the entry bundle found no `idempotency` string, but lazy chunks could not be
enumerated. Treat forum image upload as broken in production until #705 is
deployed.

#### Delivered

- **#702** `9e0a813` — `ImageChooserBlock` → `ImageBlock`; migrations 0037/0038
  (bodies **and** revisions; empty `Image.description` → `decorative: true`,
  because `ImageBlock.clean()` refuses "no alt text and not decorative" and the
  naive mapping would make the whole back-catalogue un-editable in the CMS);
  permissive reader / strict writer split in `sanitize.py`; `decorative` added
  to the read envelope (additive, so #702 could land ahead of the frontend).
- **#703** `351425c` — write shape `{image, alt_text, decorative}`; paste and
  drag-drop routed through the *same* validation (no second upload path);
  editable alt without re-upload; `disabled` during upload; `Idempotency-Key`
  reused across retries of one file selection.
- **#704** `3194165` — the Playwright spec, `E2E_TESTING_GUIDE.md` Test Suite 4,
  and a repointed `backend/docs/patterns/security/file-upload.md` (it still
  cited the retired django-machina `apps/forum/viewsets/post_viewset.py`).
- **#705** `e2fe42f` — the CORS fix above.

#### Bugs review caught that the tests hid

- `RecentTopicsView`'s thumbnail extractor still read the bare PK. A dict is
  truthy, so `set(...)` raised `TypeError: unhashable type: 'dict'` — a **500 on
  the home rail**. Its own tests kept passing because they seed the legacy
  shape. Sweep every reader of a value whose shape you change.
- `editor.isActive('image')` is true only for a `NodeSelection`, which
  ProseMirror creates after an insert only when the image is the whole document.
  Gating the alt-edit button on it left the headline feature **permanently
  disabled** in every real post — and the test passed because it mounted an
  empty document. A fixture must have the shape of real data.

#### Not done, deliberately

- **Save → reopen has no browser coverage.** AC 5's serialization and AC 6's
  rehydration are verified in jsdom and by backend tests, not in a browser. Filed
  as **todo 368** rather than checked off as browser-verified — the CORS defect
  above is same-feature proof that those are different claims.
- The CodeQL `js/xss-through-dom` alert on #703 is a **pre-existing false
  positive**: the flow is
  `event.target.files → URL.createObjectURL(file) → previewUrl → <img src>`, and
  `main` carries it identically at `TipTapEditor.tsx:154/170/172`. CodeQL taints
  `File`/`FileList` and does not model `createObjectURL` as a barrier. Not a
  required check; the ruleset threshold is `critical`, this is `high`. Dismissing
  it is the repo owner's call. Precedent: alert #116, todo 353.
- Follow-ups noted during the audit and left unfiled-in-code: `uploadPostImage`
  throws a plain `Error` rather than `ForumApiError` (the composer cannot
  distinguish 413/429/400); no cancel path in the alt prompt; no client-side
  compression on this path; no per-post image cap; no EXIF stripping; and the
  API-vs-CMS upload-ceiling divergence documented in `upload_validation.py:1-8`.

### 2026-09-07 - Completed

- Verification: all 8 acceptance criteria pass, with the per-AC evidence and the
  "verified where" qualifiers in the ledger above.
- Review: bundled `/code-review` on each PR; two BLOCKING findings repaired
  (the home-rail 500 and the permanently-disabled alt button), one MEDIUM
  (a false rationale for `MAX_ALT_TEXT_LENGTH`) repaired by splitting the
  permissive reader from the strict writer.
- Residual browser coverage filed as todo 368.
