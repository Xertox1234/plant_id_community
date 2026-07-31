---
status: pending
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

- [ ] An image picked from the device is uploaded and appears as an `image`
      block in the composed body — test with a fake API
- [ ] A rejected upload surfaces the error and leaves the drafted text intact —
      test
- [ ] Bold/italic/link/list/inline-code round-trip through compose → render —
      test per mark
- [ ] `flutter test` passes; `flutter analyze` clean

## Work Log

### 2026-07-31 - Promoted out of todo 279

- Todo 279 was a parking todo whose only AC was "prioritize the above into
  concrete slices". Per `CLAUDE.md` → Review Doc Tracking, promote-all is the
  only terminal state for a parking epic — re-deferring keeps it open forever.
  Its 9 deferred items were grouped into 5 todos by what ships together, not
  split 1:1.

## Notes

p3. Promoted from todo 279 on 2026-07-31. The image half is worth doing alone
if the rich-text half slips — they are sequenced, not coupled.
