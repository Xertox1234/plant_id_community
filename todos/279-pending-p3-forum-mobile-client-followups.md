---
status: pending
priority: p3
issue_id: "279"
tags: [forum, flutter, mobile]
dependencies: ["260"]
---

# Forum mobile client — deferred follow-ups

## Problem

Todo 260 shipped the native Flutter forum client scoped to its acceptance
criteria: read path (boards → topics → thread + 5-block StreamField renderer),
offline delta-sync (`/sync/` with tombstones), and the idempotent write path
(create topic + reply with pending-moderation surfacing), plus read-only/toggle
reactions. Several items from that epic's Recommended Action were deliberately
deferred to keep the first PR reviewable and mergeable in one pass. This todo
tracks them.

## Deferred scope (from todo 260)

1. **Image-in-composer** — the composer is text-first (emits `paragraph`
   blocks). Wire `image_picker` + `POST /forum/images/` (multipart, field
   `image`, 4-layer validated) → append an `image` body block referencing the
   returned id. Backend + `ForumImageBlock` render path already exist.
2. **Edit / delete** — `PATCH /forum/posts/{id}/` (returns `moderation_status`)
   and `DELETE /forum/posts/{id}/` (204; opening posts can't be deleted). Gate
   on `post.canEdit` / `post.canDelete`. Edit reuses the idempotency pattern.
3. **FCM push-tap deep-linking** — the whole `onMessage` /
   `onMessageOpenedApp` / `getInitialMessage` / background-handler subsystem is
   still unbuilt (todo 260 AC4's "receives a push" is already proven; only the
   tap→screen routing remains). The new `/forum/topics/:id` param route added
   in 260 is the deep-link target foundation. See todo 272 item 1 for the iOS
   APNs provisioning residue.
4. **Subscriptions** — `POST`/`DELETE /forum/topics/{id}/subscription/`; surface
   `TopicDetail.isSubscribed` with a subscribe toggle on the thread screen.
5. **Notifications list** — `GET /forum/notifications/` (cursor),
   `unread-count/`, `mark-read/`; a notifications screen + unread badge.
6. **Search** — `GET /forum/search/?q=&board=` (offset-paged, `*_has_more`).
7. **Public profiles** — `GET /forum/users/{username}/`; make author
   names/avatars tap through to a profile screen (they render inert today).
8. **Reply-visibility after posting** — a new reply on a multi-page thread lands
   on the last page, so it isn't visible after posting (only page 1 is
   refetched). Mirror the web's `collectAllPosts` / deep-link-to-post behavior.
9. **Rich composer** — the text composer only emits `paragraph` (bold/italic/
   links/lists/mentions/inline-code are rendered on read but not authorable on
   mobile). Optional parity with the web TipTap editor's FORUM allowlist.

## Technical Details

- Client lives in `plant_community_mobile/lib/features/forum/`; models,
  services (`ForumApi`), providers, screens, widgets are all in place.
- The `ForumApi` interface is the seam to extend for edit/delete/image/
  subscription/notification/search endpoints; add methods + fakes.
- Codegen gate: editing `@riverpod` sources needs `build_runner` regen (commit
  the `.g.dart`; a clean rebuild is required — incremental can miss the hash).

## Acceptance Criteria

- [ ] Prioritize the above into concrete slices (Flutter-client wave of the
      forum app-loop roadmap) — this is a tracking/grouping todo, not a single
      unit of work; split per item as picked up.

## Work Log

### 2026-07-25 - Created from todo 260 (deferred scope)

- Split off so the deferrals from the mobile-forum-client epic are visible
  rather than silently dropped.
