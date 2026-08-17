---
status: in_progress
priority: p3
issue_id: "294"
tags: [forum, flutter, mobile, composer]
dependencies: ["260"]
source_review: "todo 279 (promoted 2026-07-31)"
---

# Mobile forum composer: images and rich text

## Problem

The mobile composer is text-first — it emits only `paragraph` blocks. Images
cannot be attached at all, and bold/italic/links/lists/mentions/inline-code are
**rendered** on read but not authorable on mobile. On a plant forum, where the
question is usually "what is wrong with this leaf", not being able to attach a
photo from the composer is the sharper of the two gaps.

## Findings

- Deferred items 1 and 9 of todo 279 (from todo 260's Recommended Action),
  grouped: both are "what the composer can emit".
- Image path is ready end to end except the client: `POST /forum/images/`
  (multipart, field `image`, 4-layer validated) returns an id, and the
  `ForumImageBlock` render path already exists — the composer just needs to
  append an `image` body block referencing it.
- The web composer's TipTap FORUM allowlist is the parity target for rich
  text; the renderer already handles all of it.
- Upload is security-sensitive: the backend validates extension, MIME, size and
  PIL-decode, and a settable image reference is checked against the caller's
  own uploads within the forum collection. The client must not assume an id is
  usable just because the upload returned one.

## Recommended Action

1. Images first — higher value on this product, and independent of the
   rich-text work. `image_picker` → `POST /forum/images/` → append an `image`
   block referencing the returned id.
2. Rich text second, scoped to the web FORUM allowlist. Do not invent
   mobile-only marks the renderer cannot display.
3. Handle upload failure explicitly: a rejected image (size/MIME/decode) must
   leave the composed text intact, not discard the draft.

## Technical Details

- Client lives in `plant_community_mobile/lib/features/forum/` — `models/`,
  `providers/`, `screens/` (`forum_topics_screen.dart`,
  `forum_thread_screen.dart`, `forum_composer_screen.dart`), `services/`
  (`forum_api.dart`, `forum_composer_controller.dart`, `forum_sync_service.dart`,
  `forum_sync_store.dart`), `widgets/`.
- `ForumApi` (`services/forum_api.dart`) is the seam to extend: add the method
  plus its fake, mirroring the existing endpoints.
- Codegen gate: editing a `@riverpod` source needs
  `flutter pub run build_runner build --delete-conflicting-outputs` and a
  committed `.g.dart`. CI blocks on this; local `flutter analyze` does NOT
  catch it. A clean rebuild is required — incremental can miss the hash.
- Read `plant_community_mobile/docs/patterns/riverpod.md` and
  `.../flutter-patterns.md` before writing.

## Acceptance Criteria

- [x] An image picked from the device is uploaded and appears as an `image`
      block in the composed body — test with a fake API
- [x] A rejected upload surfaces the error and leaves the drafted text intact —
      test
- [ ] Bold/italic/link/list/inline-code round-trip through compose → render —
      test per mark → split to **todo 312** on 2026-08-17 (advisor consult:
      needs a new rich-text editing surface — no such widget exists in the
      app today — plus resolving a load-bearing interaction with todo 292's
      `isSingleEditableParagraph` gate, a materially different scope than
      the image half above). Re-pointed, not done — see todo 312 for its
      own AC.
- [x] `flutter test` passes; `flutter analyze` clean

## Work Log

### 2026-07-31 - Promoted out of todo 279

- Todo 279 was a parking todo whose only AC was "prioritize the above into
  concrete slices". Per `CLAUDE.md` → Review Doc Tracking, promote-all is the
  only terminal state for a parking epic — re-deferring keeps it open forever.
  Its 9 deferred items were grouped into 5 todos by what ships together, not
  split 1:1.

### 2026-08-17 - Image half implemented (advisor-scoped)

- Advisor consult confirmed the split the todo's own Notes had already
  flagged: the image half has a complete, tested backend contract and needs
  no new UI paradigm; rich text needs a genuinely new editing surface plus a
  load-bearing interaction with todo 292's `isSingleEditableParagraph` gate.
  Split rich text to **todo 312**, re-pointed (not checked off) above.
- **Backend read (no backend changes)**: `PostImageUploadView`
  (`api/views.py`) — `POST /forum/images/`, multipart `image` file + optional
  `alt`, Idempotency-Key supported, returns `{id, url, alt, width, height}`.
  Confirmed the WRITE shape via `api/sanitize.py::validate_forum_body` — an
  `image` block's write `value` is the bare integer PK, NOT the
  `{id, url, ...}` object the read/upload-response shape uses (a real
  divergence the advisor flagged as a likely mistake point; a client-side
  fake would have silently accepted either shape). Confirmed
  `_allowed_uploader_ids` lets the acting user always reference their own
  fresh upload, on both create and edit.
- **New**: `forum_image_picker.dart` (`ForumImagePicker` interface +
  `DeviceForumImagePicker`, wrapping `image_picker` behind an app-owned seam
  so widget tests can fake it without touching platform channels — same
  convention as `ForumApi`/`AuthService`). `ForumImageBlock.fromUploadResponse`
  (reuses the existing model — same fields as the read-body shape) and
  `buildImageBlockBody(int imageId)` (the write-shape helper, in
  `forum_body_block.dart`).
- **Changed**: `ForumApi`/`HttpForumApi` gained `uploadImage` (multipart via
  `FormData`/`MultipartFile`, reusing the existing `_idempotent()` header
  helper). `ForumComposerController` gained `uploadImage()` (reuses the same
  key-rotation mechanism as `submitTopic`/`submitReply` — a retry of the
  SAME file path replays); `submitTopic`/`submitReply` gained an optional
  `imageId` param, appending a write-shape `image` block after the paragraph
  (an image with no caption text sends an image-only body — no paragraph
  block at all). `forum_composer_screen.dart` gained an "Add photo" button
  (topic/reply only, not edit — todo 292's edit scope unchanged), a
  `CachedNetworkImage` thumbnail preview with a remove button (matching the
  existing `ForumBodyRenderer` image-rendering convention, not a raw
  `Image.network` — deliberate, avoids a widget-test hang described below),
  and `_canSubmit` now accepts text-empty-but-image-attached as valid.
- A failed upload (`_addPhoto`'s catch block) never touches the title/body
  `TextEditingController`s — they are separate state the image flow doesn't
  reach, so AC2 ("leaves the drafted text intact") holds by construction, not
  by a special-cased guard; proven by a widget test.
- **Test-infra note**: the composer's success-path widget test needed
  `replyStatus = ForumModerationStatus.pending` (staying on the pending view)
  rather than the default published path — `ForumComposerScreen` in that
  test is `MaterialApp`'s ROOT route, so a published-path `Navigator.pop`
  has nothing to pop back to. Mirrors the existing "notify-and-return" test's
  same workaround, not a new pattern. Also: the initial "Add photo" tap must
  use bounded `tester.pump()` calls, not `pumpAndSettle()` — the attached
  thumbnail's `CachedNetworkImage` placeholder spinner never resolves in the
  test harness's blocked-network environment (every HTTP request 400s),
  which hung `pumpAndSettle` (confirmed empirically — the exact
  "pumpAndSettle timed out" failure reproduced before the fix).
- Verification:

  ```
  $ flutter analyze lib/ test/
  Analyzing 2 items...
  No issues found! (ran in 0.9s)

  $ flutter test
  00:10 +271 ~3: All tests passed!
  ```

### 2026-08-17 - Code review (2 HIGH, 1 MEDIUM, all fixed)

- Dispatched `code-review-orchestrator`. Verified against primary sources
  (backend `sanitize.py`, `idempotency.py`, `PostImageUploadView`) before
  accepting findings:
  - **HIGH** — `_canSubmit` never checked `_uploadingImage`: a "Post" tap
    landing before an in-flight upload resolved submitted with
    `imageId: null`, silently dropping the attachment (the upload's own
    success handler later no-ops post-navigation via `!mounted`). **Fixed**:
    `_canSubmit` now returns `false` while `_uploadingImage`. Mutation-tested
    — reverting reproduced the exact predicted symptom (`Post` button
    re-enabled with a non-null `onPressed` while the upload was still
    gated).
  - **HIGH** — `_addPhoto`'s `pickImagePath()` call sat OUTSIDE the
    try/catch that gives upload failures graceful degradation, so a
    platform-level failure (e.g. a previously-denied photo-library
    permission — a real, reachable case, not hypothetical) propagated
    unhandled instead of surfacing via `_imageError` like an upload
    rejection does. **Fixed**: moved the picker call inside the try.
    Mutation-tested — reverting reproduced the unhandled-exception failure.
  - **MEDIUM** — no test drove the actual production sequence (upload →
    submit → fail → retry on one controller), the exact sequence the
    reviewer was asked to check for a partial-upload-then-failed-submit gap.
    By inspection the behavior was already correct (a retry keeps the same
    `imageId` and reuses the key, verified against `idempotency.py`'s
    per-scope cache-key namespacing), but nothing proved it. **Fixed**:
    added a controller test driving exactly that sequence.
  - 4 INFO-level findings confirmed as non-issues (write-shape correctness,
    the `CachedNetworkImage` bounded-pump test workaround, idempotency-key
    scoping across action types, and a pre-existing/out-of-scope iOS
    Info.plist permission-description gap predating this todo). 1 LOW
    (orphaned-image storage hygiene) accepted, not fixed — no IDOR exposure,
    a backlog-worthy cleanup-job concern, not a correctness bug.
- Added 2 new widget tests (picker-level failure surfaces gracefully; Post
  disabled during an in-flight upload, using a `Completer`-gated fake to
  hold the upload open) and 1 new controller test (upload → submit-fail →
  retry keeps the same imageId and key).
- Verification after repair:

  ```
  $ flutter analyze lib/ test/
  Analyzing 2 items...
  No issues found! (ran in 1.3s)

  $ flutter test
  00:20 +274 ~3: All tests passed!
  ```

## Notes

p3. Promoted from todo 279 on 2026-07-31. The image half is worth doing alone
if the rich-text half slips — they are sequenced, not coupled. Image half
shipped 2026-08-17; rich text split to todo 312.
