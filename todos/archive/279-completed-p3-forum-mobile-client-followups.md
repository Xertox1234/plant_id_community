---
status: completed
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

- [x] Prioritize the above into concrete slices (Flutter-client wave of the
      forum app-loop roadmap) — this is a tracking/grouping todo, not a single
      unit of work; split per item as picked up.

## Promotion map (2026-07-31)

Every one of the 9 deferred items is promoted. Nothing is re-deferred — per
`CLAUDE.md` → Review Doc Tracking, promote-all is the only terminal state for a
parking todo, because re-deferring keeps it open forever.

| Deferred item | Promoted to |
| --- | --- |
| 8. Reply-visibility after posting | **todo 291** (p2) |
| 2. Edit / delete | todo 292 |
| 3. FCM push-tap deep-linking | todo 293 |
| 4. Subscriptions | todo 293 |
| 5. Notifications list | todo 293 |
| 1. Image-in-composer | todo 294 |
| 9. Rich composer | todo 294 |
| 6. Search | todo 295 |
| 7. Public profiles | todo 295 |

Grouped by what ships together rather than split 1:1 — 9 one-item todos would
have been bookkeeping, not planning (precedent: todo 263 produced 4 from a
comparable list, todo 272 produced 3).

- **291 is p2, not p3** — the only item in the list that is a *defect* rather
  than absent functionality, and its failure mode (a successful write that
  leaves no visible trace) actively invites duplicate posts.
- **293 groups three items** because subscriptions, the notifications list and
  push-tap routing are one loop: subscribing generates what the list shows and
  the tap opens. Shipping them apart means shipping a list with nothing in it.
- **294 groups two** because both answer "what can the composer emit"; the
  image half is sequenced first and is worth shipping alone if the rich-text
  half slips.
- **295 groups two** because both are read-only discovery over endpoints that
  already exist.

## Work Log

### 2026-07-31 - Closed by promote-all (run 2026-07-31-0411)

- All 9 deferred items promoted into todos 291–295 (see the Promotion map
  above). Each carries `source_review: "todo 279 (promoted 2026-07-31)"`,
  `dependencies: ["260"]`, and concrete acceptance criteria — this todo's items
  were feature *descriptions*, not testable criteria, which is why it could
  never be finished as written.
- Verification for this todo is the files existing, not a command: its AC is a
  planning outcome. Evidence quoted in the run summary
  (`git status --short` showing the five new todo files).
- Facts re-checked against the code before promoting rather than trusted from
  the 2026-07-25 text: the client layout under
  `plant_community_mobile/lib/features/forum/` (models/providers/screens/
  services/widgets, with `forum_api.dart` as the seam) is as described, and
  each item's backend endpoint was confirmed to exist. Two details were added
  that the original list did not carry and that change how the work is done:
  search is **offset**-paged with `*_has_more` (not cursor-paged like the other
  lists, so it needs its own paging code), and forum notification copy now
  lives in a single backend table (`apps/forum_host/notification_copy.py`,
  todo 287) rather than being duplicated per surface.

### 2026-07-25 - Created from todo 260 (deferred scope)

- Split off so the deferrals from the mobile-forum-client epic are visible
  rather than silently dropped.
