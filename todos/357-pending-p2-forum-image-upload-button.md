---
status: pending
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

- [ ] Clicking or keyboard-activating **Insert image** opens the file picker;
      the control has an accessible name and works at mobile widths.
- [ ] Unsupported MIME types and files over the configured size limit are
      rejected before upload, with an announced actionable error; selecting
      the same file again after an error works.
- [ ] The author is prompted for alt text before upload; both authored alt text
      and an intentional empty/decorative alt value are handled correctly.
- [ ] A valid image submits one authenticated multipart request to the forum
      image endpoint, shows a loading state, and reports upload failures without
      losing the draft.
- [ ] A successful response inserts an image node carrying the server image id;
      new threads, replies, and edits serialize it as an `image` body block.
- [ ] Editing an existing post rehydrates the image and preserves its id; the
      rendered post uses the safe image URL and stored alt text.
- [ ] Add or update service, component, serialization round-trip, and browser
      coverage for the complete path; no test relies on a real external image
      service or committed credentials.
- [ ] `npm run type-check`, `npm run lint`, focused tests, and the relevant
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
