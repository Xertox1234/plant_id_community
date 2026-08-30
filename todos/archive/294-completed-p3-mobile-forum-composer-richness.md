---
status: completed
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
- [x] Bold/italic/link/list/inline-code round-trip through compose → render —
      test per mark → split to **todo 314** on 2026-08-17 (advisor consult:
      needs a new rich-text editing surface — no such widget exists in the
      app today — plus resolving a load-bearing interaction with todo 292's
      `isSingleEditableParagraph` gate, a materially different scope than
      the image half above). (Renumbered from 312 on 2026-08-28: 312
      collided with an unrelated auth-e2e todo filed on main via #559 after
      this split.) Resolved via todo 314 — PR #574 merged 2026-08-29,
      `ff91c9c`; see todo 314's archived file for its own AC evidence.
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
  Split rich text to **todo 314** (renumbered from 312 on 2026-08-28 — see
  below), re-pointed (not checked off) above.
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

### 2026-08-28 - Rebased PR #557 onto current main, renumbered the 312 collision

- PR #557 had gone stale (11 days, `mergeable: CONFLICTING`) against a main
  that absorbed several more forum-touching PRs since this branch was cut
  (todo 292 edit/delete #555, todo 293 subscriptions/notifications #556,
  todo 283 bookmarks #549, todo 303 cache mixin #545, among others). Disarmed
  the stale auto-merge first (`gh pr merge 557 --disable-auto`) before
  touching anything, per standing "review diff before arming" policy.
- Confirmed Canopy PR 4 (#558) — the largest intervening change — never
  touched `plant_community_mobile/lib/features/forum/` at all, so this was a
  genuine conflict-resolution, not a re-derive-from-scratch situation.
- `git merge origin/main` produced exactly 2 conflicts, both purely additive
  (this branch's `uploadImage`/image fixtures next to main's
  `subscribeToTopic`/notification fixtures in the same interface/class):
  `forum_api.dart` (interface section only — the `HttpForumApi`
  implementation merged clean) and `forum_test_support.dart`
  (`FakeForumApi` field block + method-implementation block). Merged both
  sides in, nothing dropped.
- **Caught during resolution**: the PostToolUse Dart formatter hook ran
  against `forum_test_support.dart` while it still had unresolved
  `<<<<<<<` markers (mid multi-block resolution), and its parse-failure
  recovery path silently inserted the token `void` before two type names —
  `class FakeAuthService extends void AuthService` and
  `class FakeForumImagePicker implements void ForumImagePicker`. Neither
  parent branch had this; `dart format --set-exit-if-changed` on the file
  caught it immediately (`Expected a type name`). Fixed by hand, confirmed
  a repo-wide `grep -rn "extends void \|implements void "` came back clean
  afterward. Lesson: resolve every conflict block in a file in one edit —
  don't leave a file with markers still present between edits, since an
  auto-formatter can run on it mid-resolution.
- Renumbered the split-out rich-text todo: **312 → 314**. It had collided
  with an unrelated `312-pending-p3-auth-e2e-spec-two-stale-failures.md`
  filed on main via #559 four days after this todo split rich text out to
  312. `git mv` + `issue_id` frontmatter updated in the new file; both
  re-point references above updated 312 → 314 (the AC3 line and the
  2026-08-17 Work Log entry) so the pointer stays live, not falsified.
- Verification after merge (full suite, not the forum subset — this touched
  shared test-support fixtures used across the forum test tree):

  ```
  $ dart format --output=none --set-exit-if-changed lib/features/forum/services/forum_api.dart test/features/forum/support/forum_test_support.dart
  Formatted 2 files (0 changed) in 0.01s

  $ flutter test
  00:07 +290 ~3: All tests passed!
  ```

  (290 vs. the 274 recorded 2026-08-17 — main brought in more tests via the
  intervening PRs; nothing here removed coverage.)
- Pushed `fa156f4`. PR #557 mergeable state flipped `CONFLICTING` →
  `MERGEABLE`. Re-arming auto-merge pending a clean CI run (previous run
  showed `Detect mobile changes`/`mobile-ci-gate`/npm-scan failures that are
  very likely artifacts of GitHub being unable to materialize the merge ref
  while `CONFLICTING` — re-verifying on the fresh push before concluding
  that, per advisor guidance).

### 2026-08-29 - Reconciled and closed out

- Both halves of this todo's scope confirmed merged and CI-green on
  `origin/main`, with nothing left to implement:
  - **Image half (this todo's own scope)**: PR #557, commit `a2c5938`, all
    17 CI checks SUCCESS.
  - **Rich-text half (split to todo 314)**: PR #574, commit
    `ff91c9c89aabc4c79a23caf2baff531f3601d452`, merged
    2026-08-29T03:49:02Z, all 17 CI checks SUCCESS including `Flutter
    analyze, test, and debug build`.
- Neither todo file had been archived because local `main` in this checkout
  had drifted ~40 commits behind `origin/main` across several intervening
  sessions/worktrees — the merges themselves went through cleanly (each PR
  had its own full review cycle, documented above and in todo 314's own Work
  Log), but the archival bookkeeping step was never run against the synced
  state. `git fetch origin main` + branching directly off `origin/main`
  surfaced both merges; no new application code changes were needed here.
  Todo 314's own file was updated and archived in the same pass (it had only
  a "split out" entry despite its implementation branch,
  `worktree-todo-314-composer-rich-text`, already being the exact source of
  the merged PR #574).
- Checked off AC3 above now that its re-pointed destination (todo 314) has
  itself reached `completed` — per CLAUDE.md's Review Doc Tracking
  convention, a re-pointed item stays unchecked only while its destination
  is still open; once the destination ships, the source reference is
  checked off with a completion date, same as `- [x] #42 (completed
  YYYY-MM-DD)`.
- Re-ran verification fresh on the reconciliation branch (both PRs present):

  ```
  $ flutter test
  00:24 +420: All tests passed!

  $ flutter analyze lib/ test/
  Analyzing 2 items...
  No issues found! (ran in 2.3s)
  ```

## Notes

p3. Promoted from todo 279 on 2026-07-31. The image half is worth doing alone
if the rich-text half slips — they are sequenced, not coupled. Image half
shipped 2026-08-17 (PR #557); rich text split to todo 314 (renumbered from
312 on 2026-08-28 — see Work Log), shipped 2026-08-29 (PR #574). Both halves
confirmed merged and archived 2026-08-29.
