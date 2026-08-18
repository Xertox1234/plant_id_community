---
status: completed
priority: p3
issue_id: "292"
tags: [forum, flutter, mobile]
dependencies: ["260"]
source_review: "todo 279 (promoted 2026-07-31)"
---

# Mobile forum: post edit and delete

## Problem

The Flutter forum client can create topics and replies but cannot edit or
delete them — the backend endpoints and the per-post capability flags both
exist and are simply unused by the mobile client. A user who typos a reply on
mobile has to open the web app to fix it.

## Findings

- Deferred item 2 of todo 279 (from todo 260's Recommended Action).
- Backend is ready: `PATCH /forum/posts/{id}/` returns `moderation_status`, and
  `DELETE /forum/posts/{id}/` returns 204. Opening posts cannot be deleted.
- The serializer already ships `can_edit` / `can_delete` per post — the client
  has the gating data and ignores it.
- The frozen-topic guard is deliberately symmetric: PATCH and DELETE are both
  409 on a closed/locked topic **including for moderators** (a product
  decision, see `docs/rules/forum.md`). The mobile UI must surface that 409,
  not treat it as an error to retry.

## Recommended Action

1. Add `editPost` / `deletePost` to `ForumApi` plus their fakes.
2. Gate the affordances on `post.canEdit` / `post.canDelete` — do not
   re-derive ownership client-side.
3. Edit reuses the idempotency pattern already used by create. Per
   `docs/rules/flutter.md`: one `Idempotency-Key` per action, **rotated when
   the composed content changes** — an edit-then-retry with a stale key wedges
   a permanent 422.
4. Surface `moderation_status` on the edit response the way the create path
   already surfaces pending moderation; an edit can send a post back to the
   queue.

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

- [x] Edit and delete are reachable from a post the user owns, and absent on
      one they do not — widget test asserting both
- [x] An edit that returns `moderation_status: pending` surfaces that state
      rather than silently showing the old body — test
- [x] A 409 on a frozen topic surfaces as a clear message, not a retry — test
- [x] Editing then retrying with changed content does not 422 (key rotation) —
      test
- [x] `flutter test` passes; `flutter analyze` clean

## Work Log

### 2026-07-31 - Promoted out of todo 279

- Todo 279 was a parking todo whose only AC was "prioritize the above into
  concrete slices". Per `CLAUDE.md` → Review Doc Tracking, promote-all is the
  only terminal state for a parking epic — re-deferring keeps it open forever.
  Its 9 deferred items were grouped into 5 todos by what ships together, not
  split 1:1.

### 2026-08-17 - Implemented

**`ForumApi`**: `editPost`/`deletePost` added (PATCH/DELETE
`/forum/posts/{id}/`, matching `PostWriteView.patch`/`.delete` exactly —
verified against the backend source, not assumed). `EditPostResult` wraps
the full `PostSerializer` response shape + `moderation_status` (new class in
`forum_write_results.dart`). `deletePost` carries no idempotency key — the
backend's `delete()` has none (only `patch()` does), and a repeat DELETE of
an already-gone post 404s, which is naturally idempotent enough.

**Ownership gating**: `PostCard`'s new `_PostMenu` shows Edit/Delete each
gated on BOTH the caller-supplied callback being non-null AND the post's own
`canEdit`/`canDelete` — never re-derived client-side, straight from the
server-computed flags already on `ForumPost`.

**Idempotency**: `ForumComposerController.submitEdit` reuses the exact
`_refreshKeyForContent` rotation already proven by `submitReply`/`submitTopic`
— same key on a same-content retry, fresh key when the edited text changes.

**Rich-content safety (the substantive design decision this todo required)**:
the mobile composer is text-first (todo 294 is the separate rich-text/image
authoring gap), so editing a post whose body isn't safely round-trippable
through plain text risks silent data loss. `isSingleEditableParagraph` gates
this — initially block-shape-only (one paragraph block), **strengthened
during code review** (see below) to also verify the paragraph's HTML
contains no real markup beyond `buildParagraphBody`'s own escaped-text-plus-
`<br>` shape, since a web-authored post using only inline marks
(bold/italic/links) ALSO collapses to one paragraph block but carries real
tags. When the body doesn't qualify, `ForumComposeArgs.edit` leaves the
field empty and `hasNonTextContent` triggers a warning banner in the
composer ("This post has formatting or an image the app can't show here
yet — saving will replace it with plain text") rather than silently
discarding content.

**409 handling (AC3)**: verified `Post.edit_block`/`delete_block`
(`models/posts.py`) return specific, human-readable, non-retry-implying
messages ("Post is locked.", "Topic is closed or locked.", "Opening posts
cannot be deleted via the API.") for the permanent frozen/locked-state 409 —
distinct from the create/reply path's transient idempotency-in-flight 409
(`reserve()`'s "A request with this Idempotency-Key is being processed."),
which genuinely IS retry-worthy. Both share the same `Conflict` exception
class server-side with no machine-readable discriminator beyond the message
text, so edit/delete's 409 handler shows the backend message VERBATIM rather
than reusing create/reply's generic "tap Post again to retry" copy, which
would be actively wrong for the permanent case.

**State updates without losing scroll depth**: `TopicPosts.applyEditedPost`/
`.deletePost` splice the change into the already-loaded page(s) directly,
deliberately NOT `ref.invalidate`-and-refetch — `TopicPosts.build()` only
ever fetches page 1, so invalidating on a long thread where the user had
`loadMore`'d further would silently drop those pages. Mirrors the existing
`toggleReaction` splice pattern.

**Verification**: `flutter analyze` clean throughout. `flutter pub run
build_runner build --delete-conflicting-outputs` run twice (once after the
initial implementation, once after the review-repair pass) — the first run
changed `forum_providers.g.dart` by exactly one line (`_$topicPostsHash()`,
since the source hash covers the whole `TopicPosts` class, not just
`build()` — confirmed empirically rather than assumed); the second run (after
fixes that didn't touch `forum_providers.dart`) produced an identical,
already-committed diff, confirming stability. `check_flutter_security.py`
passes (info-only dependency-update notices, pre-existing).

**Known issues — none unaddressed.** Code review (below) is the next gate.

### 2026-08-17 - Code review + repair

Dispatched a review agent against the full diff (16 files). It cross-checked
the implementation against the actual backend source (`PostWriteView`,
`Post.edit_block`/`delete_block`, `PostSerializer`) and the web client's
`htmlToBodyBlocks` — not a read-through, an empirical/source-verified pass,
including one finding reproduced with a minimal `go_router` widget test
against this project's actual `go_router` version. 5 findings (2 HIGH, 2
LOW, 1 INFO) — fixed all 4 actionable ones:

1. **[HIGH, reproduced]** `_PendingView`'s "Done" button unconditionally
   popped `false` (a `bool`), but `_openEdit` pushes the composer as
   `context.pushNamed<ForumPost>(...)` while reply/topic push as `<bool>` —
   popping a `bool` against a `<ForumPost>`-typed route throws inside
   go_router (`ImperativeRouteMatch.complete`), stranding the user on the
   pending-moderation screen with an uncaught exception. AC2's own scenario
   (an edit sent back to moderation) is exactly what triggers this — the
   existing pending test only asserted the banner text, never tapped Done.
   **Fixed**: pop with no value (`Navigator.of(context).pop()`, i.e. `null`)
   instead of the literal `false` — `null` is valid for any `T?` regardless
   of which generic the route was pushed with, and every caller already
   treats a non-success pop as "nothing to apply". New regression test
   drives the full router-based flow (edit → pending → tap Done) and asserts
   `tester.takeException()` is null; mutation-tested by reverting to the
   literal `false` and confirming the exact reproduced `TypeError` returns.

2. **[HIGH, source-verified both sides]** `isSingleEditableParagraph` gated
   purely on block SHAPE (one paragraph block), not content safety. A
   web-authored post using only inline marks (bold/italic/links, no image,
   no top-level blockquote) collapses to exactly one `paragraph` block too
   (confirmed against the web client's `htmlToBodyBlocks` and the backend's
   nh3 `ALLOWED_TAGS`), but its HTML is real markup, not
   `buildParagraphBody`'s escaped-text shape — so it silently passed the
   "safe to edit" gate, pre-filled as literal `&lt;strong&gt;` tag-soup text
   with NO warning, and saving would permanently burn that corruption in.
   **Fixed**: strengthened the check to verify the paragraph's HTML,
   stripped of every real `<br>`, contains no leftover `<`/`>` — an exact
   test for "this HTML could only have come from the mobile composer",
   since `buildParagraphBody` only ever emits `<br>` as a literal tag and
   escapes every other angle bracket. New tests cover both the correct-true
   cases (mobile-shaped output, including a user who literally typed the
   text "<br>") and the correct-false case (real `<strong>`/`<a href>`
   markup); mutation-tested by reverting to the shape-only check and
   confirming the new "real markup" test goes red.

3. **[LOW]** The logged-out prompt's action text (`_LoginPrompt`) had a
   `_isTopic ? ... : 'reply'` ternary that never branched for edit mode,
   showing "Log in to reply." when opening edit while logged out. **Fixed**:
   added the third branch, matching the pattern already used a few lines
   away for `title`/`labelText`.

4. **[LOW]** `_openEdit`/`_confirmDelete` only updated `TopicPosts` local
   state, never `ref.invalidate(topicDetailProvider(topicId))` the way
   `_openReply` does — a delete in particular leaves `reply_count` stale
   until the user leaves and returns. **Fixed**: added the same invalidate
   call after a successful edit/delete, matching the reply path; this is a
   separate, cheap single-object provider, unrelated to the paged-state
   preservation `applyEditedPost`/`deletePost` exist to protect.

**[INFO, not fixed — noted only]**: `plainTextFromParagraphHtml`'s
reversibility tests are pinned against `buildParagraphBody`'s OWN output,
never against what the real backend nh3 sanitizer returns after a write —
flagged as an unpinned assumption (very likely fine; ammonia/html5ever emits
bare `<br>` for HTML5 void elements), not a confirmed defect. Left as a note
for whoever next touches the sanitizer config.

**Post-repair verification**: `flutter analyze` clean. Full `flutter test`
→ 265 passed (was 262 pre-repair; +3 from the new HIGH-finding regression
tests — the go_router repro test, plus 2 new `isSingleEditableParagraph`
markup-safety tests). `build_runner` re-run, `.g.dart` diff unchanged (the
repair touched no `@riverpod` source). `check_flutter_security.py` passes.

### 2026-08-17 - Completed

- Verification: all 5 acceptance criteria passed — `flutter test` 265/265,
  `flutter analyze` clean.
- Review: 5 findings (2 HIGH, 2 LOW, 1 INFO) — both HIGH and both LOW fixed
  (4/4 actionable); the INFO item is a documented, low-risk assumption, not
  a defect, left as a note. No findings accepted-not-fixed.

## Notes

p3. Promoted from todo 279 on 2026-07-31. Related: todo 291 (the same write
path's visibility defect).
