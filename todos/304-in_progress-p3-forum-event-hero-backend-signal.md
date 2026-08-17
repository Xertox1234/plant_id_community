---
status: in_progress
priority: p3
issue_id: "304"
tags: [forum, backend, web]
dependencies: []
---

# Drive the forum event hero from a backend signal, not client-side inference

## Problem

The landing page's "Community event" hero is inferred client-side:
`recentTopics.find(t => t.is_pinned && t.slug.startsWith('bloom-watch'))`
over a 20-row recency window, with hardcoded "Every August" copy. Three
drift modes (PR #538 round-2 review): 20 newer topics evict the still-live
pinned event mid-event (backend orders by `-last_post_at`, no pinned boost);
the August copy persists into winter while the topic stays pinned; and the
window size silently diverges if ops tune `RECENT_TOPICS_MAX_LIMIT` down.
The slug+copy coupling was the PR 2.5 spec's locked decision — fine for
launch, wrong shape long-term.

## Findings

- Hero code: `web/src/pages/forum/CategoryListPage.tsx` (~167), constant
  `RECENT_TOPICS_FETCH_LIMIT` mirrors the backend default client-side.
- Backend has no notion of a "current event"; `is_pinned` is per-board
  ordering, not a sitewide flag.

## Recommended Action

1. Backend "current event" signal — smallest honest shape: either a
   `?pinned=1` filter on `topics/recent/`, or a tiny
   `forum/event/` endpoint returning the currently-featured topic (id,
   slug, title, hero copy fields) sourced from a Wagtail setting or an
   admin-pickable chooser.
2. Web: hero renders from that signal (topic title/copy from the API);
   fall back to the evergreen "Ask the canopy" hero when absent.
3. Retire the slug-prefix inference and the hardcoded seasonal copy.

## Acceptance Criteria

- [x] Hero survives arbitrary forum activity while the event is live and
      disappears when the event is unfeatured — no recency-window coupling.
- [x] Hero copy comes from data, not a client string tied to one seed slug.
- [x] Evergreen fallback unchanged.

## Work Log

### 2026-08-15 - Filed

- Deferred out of PR #538's fix rounds: conflicts with nothing, but larger
  than a review one-liner and touches spec-locked copy. Cheap parts (window
  = server max, named constant) done in-PR.

### 2026-08-17 - Started by completing-todos skill (run 2026-08-17-0246)

- Picked up by automated workflow.

### 2026-08-17 - Implemented

Chose the "tiny `forum/event/` endpoint" option from Recommended Action
(over extending `topics/recent/` with `?pinned=1`) — keeps the change fully
decoupled from the list-envelope shapes todo 302 just pinned, and `is_pinned`
is confirmed per-topic (not per-board) but still not a "sitewide featured"
signal, so a `?pinned=1` filter on `topics/recent/` wouldn't disambiguate
multiple pinned topics across boards anyway.

**Data model** — no existing singleton/settings pattern in this codebase
(`wagtail.contrib.settings` is installed but unused by any app); `ForumIndex`
(the forum root page, already CMS-editable for `intro`) is the natural
extension point instead of inventing a new settings model:

- `ForumIndex.featured_topic` — nullable FK to `Topic`, `SET_NULL` (deleting
  the topic must not take the page down).
- `ForumIndex.featured_eyebrow` — CharField, default `"Community event"`.
- `ForumIndex.featured_description` — TextField, blank.
- `Topic.title` doubles as the hero's headline — no separate "headline"
  field, avoiding duplicate data entry for what a moderator already names
  when creating the topic.
- Migration `0022_forumindex_featured_description_and_more.py`.
- `content_panels`: `MultiFieldPanel` grouping the three fields under
  "Landing-page event hero". `Topic` is already a registered snippet
  (`TopicViewSet`), so `FieldPanel("featured_topic")` renders a proper
  chooser widget, not a raw all-topics dropdown.

**Backend** — `EventHeroView` (`wagtail_forum/api/views.py`), mirrors
`RecentTopicsView`/`ExpertsView`'s exact shape (`UnversionedForumAPIMixin,
PublicForumReadCacheMixin, APIView`, `AllowAny`, hand-built dict response —
deliberately not a serializer, same "don't become another hit builder"
reasoning as `RecentTopicsView`'s own docstring). Re-validates the featured
topic's `live` + board visibility on **every read** — trusting the FK alone
would leak a topic that got moderated away or board-restricted after being
featured. Reuses `_visible_forum_index()` (the same helper `BoardListView`
uses for `intro`) rather than inventing a second "which ForumIndex" rule.
Mounted at `GET forum/event/` in both the package
(`wagtail_forum/api/urls.py`) and the host (`forum_host/api_urls.py`,
straight from the package, no throttle wrapper — matches
`RecentTopicsView`/`ExpertsView`'s GET-only+AllowAny+cached profile, not
`SearchView`'s expensive-query throttled profile). Confirmed via the host's
own route-parity drift-guard test (`test_host_api_routes_match_package`) and
the two throttle-fixture tests, which correctly do NOT need an entry (they
only enumerate wrapped/throttled views).

**Web** — `fetchEventHero()` (`forumService.ts`) + `EventHero`/
`EventHeroTopic` types (`types/forum.ts`) + `eventHeroTopicPath()` helper
(`forumUrls.ts`, mirrors `recentTopicPath`'s id-coercion shape — DRF's
numeric ids vs `Category`/`Thread`'s string ids). `CategoryListPage.tsx`:
replaced the `recentTopics.find(t => t.is_pinned &&
t.slug.startsWith('bloom-watch'))` inference and the hardcoded "Every
August…" copy with an `eventHero` state fetched alongside the board list
(same "nice-to-have, never fails the page" `.catch()` treatment as the
recent-topics fetch). Evergreen fallback branch untouched (AC3).

**Retired-workaround cleanup**: `RECENT_TOPICS_FETCH_LIMIT` was bumped from
5→20 specifically to keep the old hero inference from scanning past a
still-pinned event (PR #538 review finding #6) — with the hero no longer
reading `recentTopics` at all, that reason is gone, so reverted it back to
5 (`ActiveNowModule` only ever displays 3 regardless). Updated the two
comments this affected (`CategoryListPage.tsx`'s constant comment,
`ActiveNowModule.tsx`'s prop doc) so they don't describe a retired
rationale — both were direct fallout of this change, not unrelated
neighboring-code cleanup.

**Mutation-tested** the visibility re-check (the safety-critical part): with
the `live=True, board__in=_visible_boards()` filter removed, both
`test_event_hero_unpublished_featured_topic_returns_null` and
`test_event_hero_restricted_board_returns_null` went red (leaked the
topic); restored via direct Edit (not git stash — this file has no prior
commit on the branch, the known stash-round-trip pitfall from todo 283)
and confirmed green + restoration verified by grep.

Verification:

```
$ python -m pytest packages/wagtail_forum/wagtail_forum/tests/api/test_event_hero.py -v
Pytest: 6 passed
$ python -m pytest packages/wagtail_forum/ apps/forum_host/
Pytest: 800 passed
$ python manage.py spectacular --file /tmp/schema-check.yaml
exit 0 (pre-existing warnings/errors in unrelated apps only; none reference EventHeroView)
$ npx tsc --noEmit
No errors found
$ ./node_modules/.bin/vitest run
Test Files  80 passed (80)
Tests  897 passed (897)
$ npm run lint
0 errors (1 pre-existing warning in coverage/block-navigation.js, unrelated)
```
