---
status: completed
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

### 2026-08-17 - Code review

Dispatched `code-review-orchestrator` (triage-only) → routed 3 domain
reviewers (wagtail-reviewer, cross-cutting-reviewer, react-typescript-reviewer),
dispatched all in parallel. 4 findings total; 3 accepted+fixed, 1 rejected
with evidence.

**Rebase note**: this branch was cut before PR #550 (todo 302) merged, so it
initially lacked that PR's README fixes. Committed a checkpoint, rebased
onto `origin/main` (clean, no conflicts), then re-verified — avoids the
git-stash-on-uncommitted-work pitfall since the checkpoint was a real commit.

1. **[medium, wagtail-reviewer, accepted]** `test_read_cache_headers.py`'s
   `_public_paths()` — the shared regression pin for every
   `PublicForumReadCacheMixin` view — wasn't swept to include `/forum/event/`,
   despite the file's own comment documenting exactly this convention for
   `topics/recent/`/`users/experts/`. Fixed: added the path; re-ran the file,
   7/7 passed.
2. **[low, wagtail-reviewer, accepted]** `EventHeroView`'s docstring said
   "this must not leak either" — true of the origin re-check, overstated for
   the CDN-cached path (a `PublicForumReadCacheMixin` response can serve a
   just-unpublished topic for up to `PUBLIC_READ_CACHE_SECONDS`). Fixed:
   softened the docstring to name the TTL-bounded tradeoff explicitly,
   matching the README's own accepted-tradeoff framing.
3. **[high, cross-cutting-reviewer, REJECTED]** Argued `EventHeroView`
   should switch to `PrivateForumReadCacheMixin` (no-store) because a
   moderated-away featured topic could linger in a CDN cache. Verified
   against the codebase's own established precedent before rejecting:
   `RecentTopicsView`, `ExpertsView`, `TopicListView`, and `BoardListView`
   are ALL `PublicForumReadCacheMixin` and expose the byte-identical risk
   (any topic in a public list/rail can be moderated away and linger in
   cache) — this is the README's own documented, deliberate tradeoff
   ("Tradeoff: a just-removed topic can linger in the anon-cached *list* for
   up to this TTL"), not a bug specific to this endpoint. `TopicListView` in
   particular is the strongest counter-evidence: it's literally the list of
   topics that can be moderated away, and it's shipped public-cached.
   Switching only `EventHeroView` to no-store would be an inconsistent,
   unmotivated exception to an established pattern, would kill CDN offload
   for the one endpoint that most wants it (landing-page hero), and the
   underlying accuracy concern the finding raises is the same one
   wagtail-reviewer's LOW finding caught and finding #2 above already fixed.
   No mixin change made.
4. **[low, react-typescript-reviewer, accepted]** `EventHeroTopic.board` and
   `RecentTopic.board` both re-typed the same `{id, name, slug}` shape
   inline. Fixed: extracted `BoardSummary` in `types/forum.ts`, both
   interfaces now reference it.

Also (self-caught, not from a reviewer): `_public_paths()`'s docstring
comment updated to mention `event/` alongside the existing
`topics/recent/`/`users/experts/` note, matching the convention it
documents.

Re-verified after all repairs:

```
$ python -m pytest packages/wagtail_forum/wagtail_forum/tests/api/test_read_cache_headers.py -v
Pytest: 7 passed
$ python -m pytest packages/wagtail_forum/ apps/forum_host/
Pytest: 801 passed
$ python manage.py spectacular --file /tmp/schema-check3.yaml
exit 0 (pre-existing warnings/errors in unrelated apps only; none reference EventHeroView)
$ npx tsc --noEmit
No errors found
$ ./node_modules/.bin/vitest run
Test Files  80 passed (80)
Tests  897 passed (897)
$ npm run lint
0 errors (1 pre-existing warning in coverage/block-navigation.js, unrelated)
```

### 2026-08-17 - Completed by completing-todos skill (run 2026-08-17-0246)

- Verification: all 3 acceptance criteria passed (backend 801/801, web
  897/897, tsc clean, lint clean, spectacular exit 0).
- Review: 4 findings from 3 domain reviewers — 3 accepted+fixed (test
  coverage gap, docstring accuracy, shared-type extraction), 1 rejected with
  evidence (HIGH severity mixin-swap claim contradicted by 4 already-shipped
  sibling endpoints sharing the identical, deliberately-accepted tradeoff).
