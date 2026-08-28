---
status: pending
priority: p3
issue_id: "317"
tags: [forum, flutter, mobile, widgets]
dependencies: ["260"]
source_review: "todo 295 (re-pointed 2026-08-28)"
---

# Mobile forum: tappable author identity → public profile screen

## Problem

Author names and avatars render inert in the mobile forum client — tapping
one does nothing, even though a public profile endpoint
(`GET /forum/users/{username}/`) already ships. Split out of todo 295, whose
"reuse the existing author widget" premise turned out to be false (see
Findings) — this is a materially larger task than the parent todo implied.

## Findings

**There is no shared/reusable author widget today.** Confirmed by research
(todo 295's dispatch, 2026-08-28): author rendering is duplicated inline,
differently, in two places:

- `PostCard` (`plant_community_mobile/lib/features/forum/widgets/post_card.dart`)
  — private `_Avatar` widget (circle + initial-letter fallback, lines
  152-181) + inline `Text(author.name)` (line 60) + `TrustBadge` (line 68),
  built from `post.author`. One call site:
  `forum_thread_screen.dart:248`.
- `TopicCard` (`plant_community_mobile/lib/features/forum/widgets/topic_card.dart`)
  — bare `Text(topic.author.name)` (line 68), **no avatar at all**. One call
  site: `forum_topics_screen.dart:116`.
- `ForumTopicListItem.lastPostAuthor` / `ForumTopicDetail.lastPostAuthor` are
  parsed from JSON but never rendered anywhere in the UI today.
- `ForumNotification.actor` is used only as `notification.actor.name`
  interpolated into a plain message string
  (`forum_notifications_screen.dart:163-181`), never as an avatar or
  tappable element.

So making authors tappable "everywhere" means **building a new shared
widget from scratch** and retrofitting `PostCard` + `TopicCard` (plus a
scope decision on whether `lastPostAuthor`/notification `actor` get
upgraded to the same treatment or stay text-only) — not adding `onTap` to
an existing component.

**Deletion handling.** `ForumAuthor.isDeleted` already exists
(`plant_community_mobile/lib/features/forum/models/forum_author.dart`) and
checks exactly the right thing: `username == '[deleted]'`. The backend's
`[deleted]` sentinel (`serializers.py::_deleted_author()`) is always a real
object with that literal username — never JSON `null` — so this is a
client-side check, not a null-guard.

**Field-parity gap**: backend `serialize_forum_author`/`_deleted_author`
return 5 fields including `title` (a moderator/role title string); mobile
`ForumAuthor.fromJson` parses only 4 and silently drops `title`. The new
profile screen (which surfaces `title` per the backend's
`PUBLIC_PROFILE_SCHEMA`) needs this field added to the model first.

**Profile endpoint response shape** (`GET /forum/users/{username}/`,
`PublicProfileView`, `AllowAny`, 404 on missing/inactive username):

```json
{
  "username": "...", "display_name": "...", "avatar": "...", "trust_level": 2, "title": "...",
  "bio": "...", "signature": "...", "post_count": 0, "joined_at": "...",
  "recent_topics": [{"id": 1, "slug": "...", "title": "...", "board_id": 1, "board_slug": "...", "reply_count": 0, "created_at": "..."}],
  "recent_posts": [{"id": 1, "topic_id": 1, "topic_slug": "...", "topic_title": "...", "board_id": 1, "board_slug": "...", "created_at": "..."}]
}
```

(max 10 items each for `recent_topics`/`recent_posts`). Excludes
`fcm_token` and `flags_received` deliberately (credential / moderation
signal).

## Recommended Action

1. Add `title` to `ForumAuthor.fromJson` (currently silently dropped).
2. Add `ForumApi.fetchProfile(username)` + fake, parsing the shape above
   into a new `ForumProfile` model.
3. Build one new shared author-identity widget (avatar + name + trust
   badge, tappable, gated on `!author.isDeleted`) and retrofit `PostCard`
   and `TopicCard` to use it instead of their current inline
   implementations. Decide explicitly whether `lastPostAuthor` and
   notification `actor` get upgraded too, or stay text-only for this slice
   — don't let scope silently expand mid-implementation.
4. Profile screen: header (avatar/name/title/trust/bio/post_count/joined),
   `recent_topics`/`recent_posts` lists (plain lists, not paginated — the
   backend caps at 10 each).

## Technical Details

- Client lives in `plant_community_mobile/lib/features/forum/`.
- `ForumApi` (`services/forum_api.dart`) is the seam to extend — mirror the
  existing method/fake pattern (15 methods already there, both
  `HttpForumApi` and `FakeForumApi` need the addition).
- Codegen gate: editing a `@riverpod` source needs a clean
  `flutter pub run build_runner build --delete-conflicting-outputs` and a
  committed `.g.dart` — CI blocks on this, local `flutter analyze` does
  NOT catch staleness.
- Read `plant_community_mobile/docs/patterns/riverpod.md` and
  `.../flutter-patterns.md` before writing.
- Shared-widget blast radius when touching `PostCard`/`TopicCard`: run the
  **full** `flutter test`, not just the forum subset (Wave 2 M6 lesson —
  shared identity rendering has bitten this exact way before).

## Acceptance Criteria

- [ ] A new shared author-identity widget exists (avatar + name + trust
      badge), used by both `PostCard` and `TopicCard`
- [ ] Tapping a real author opens their profile screen; tapping a
      `[deleted]` author does nothing — test asserting both
- [ ] Profile screen renders header + recent_topics + recent_posts from a
      real fixture shaped like `PUBLIC_PROFILE_SCHEMA`
- [ ] `ForumAuthor.title` is parsed (currently dropped) and rendered on the
      profile screen
- [ ] `flutter test` (full suite, not just forum/) passes; `flutter
      analyze` clean

## Work Log

### 2026-08-28 - Split from todo 295

- Todo 295 bundled search + tappable-author-profile as one slice. A
  research pass (dispatched while implementing 295's search half) found
  the "reuse the existing author widget" premise false — no such widget
  exists, so this half needs new-widget construction, a materially
  different and larger scope than search's "add one API method + one
  screen." Split rather than bundled, per the same re-point-not-check-off
  convention used earlier this session for todos 293/294.

## Notes

p3. Split out of todo 295 on 2026-08-28 (advisor-flagged split, confirmed
by research). Depends on the same backend contract todo 295 verified
(`serialize_forum_author`/`_deleted_author`, `PublicProfileView`) — no new
backend work needed, this is client-only.
