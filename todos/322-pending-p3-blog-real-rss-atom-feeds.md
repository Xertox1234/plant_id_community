---
status: pending
priority: p3
issue_id: "322"
tags: [backend, blog, api, feeds]
dependencies: []
---

# Blog has no real RSS/Atom feed — build one with Django's syndication framework

## Problem

The blog has no working syndication feed. Todo 307 found and deleted two
`@action`-decorated stub methods (`rss`/`atom` on `BlogFeedViewSet` in
`apps/blog/api/viewsets.py`) that were never real feeds — they returned
JSON shaped like a feed, not RSS/Atom XML, and were unrouted (unreachable)
on top of that. There is no follow-up mechanism in place, so blog posts
have zero syndication or feed-reader discoverability today.

## Findings

- Deleted in todo 307 (2026-08-30): `BlogFeedViewSet.rss`/`.atom`
  (`apps/blog/api/viewsets.py`, formerly lines ~783-816) — both returned
  `Response({"format": "rss"/"atom", ..., "posts": serializer.data})`,
  i.e. JSON, with a comment admitting "You would implement RSS XML
  generation here." Registered on a separate `blog-feeds` endpoint
  (`api_router.register_endpoint("blog-feeds", BlogFeedViewSet)`), also
  deleted — not `blog-posts`, so even the URL shape was wrong for a
  feed reader.
- The codebase already has the correct pattern, just applied to the
  **forum**, not the blog: `apps/forum_host/feeds.py` defines
  `ForumTopicsFeed(Feed)` using Django's real
  `django.contrib.syndication.views.Feed` with
  `feed_type = Rss201rev2Feed`, producing genuine RSS XML. Mounted at
  `path("forum/rss/", ForumTopicsFeed(), name="forum-rss")` in
  `plant_community_backend/urls.py:177`.
- Confirmed (todo 307 investigation) there is no RSS/Atom discovery link
  anywhere in the web frontend — `web/src/components/PageMeta.tsx`'s only
  mention of RSS is an aspirational doc-comment, not implemented markup
  (`<link rel="alternate" type="application/rss+xml">` is absent).
- No `web/src` or `plant_community_mobile/` code consumes any feed
  endpoint today — this is genuinely greenfield, not restoring something
  that broke.

## Recommended Action

1. Add `apps/blog/feeds.py` with a `BlogPostsFeed(Feed)` class mirroring
   `apps/forum_host/feeds.py`'s `ForumTopicsFeed` pattern — `title`,
   `link`, `description`, `items()` (live+public `BlogPostPage`s ordered
   by `-first_published_at`, capped at a sane limit via
   `apps/blog/constants.py`), `item_title`/`item_description`/
   `item_link`/`item_pubdate`.
2. For Atom, either add a second `Feed` subclass with
   `feed_type = Atom1Feed` or evaluate whether RSS alone is sufficient
   for launch (most feed readers handle RSS 2.0 fine; Atom is optional
   polish).
3. Mount at `path("blog/rss/", BlogPostsFeed(), name="blog-rss")` (and
   `blog/atom/` if built) in `plant_community_backend/urls.py`, next to
   the existing `forum/rss/` entry for consistency.
4. Add a discovery `<link rel="alternate" type="application/rss+xml"
   title="..." href="...">` tag to `web/src/components/PageMeta.tsx` (or
   directly on the blog list/detail pages) so feed readers and browsers
   can find it.
5. Test with Django's feed validation (`django.contrib.syndication` is
   well-tested upstream; the main risk is `items()`/`item_link()` logic)
   plus an actual XML-parse assertion in a Django test hitting
   `/blog/rss/`.

## Technical Details

- Pattern to mirror: `backend/apps/forum_host/feeds.py`,
  `backend/plant_community_backend/urls.py:177` (forum-rss mount).
- New file: `backend/apps/blog/feeds.py`.
- Mount point: `backend/plant_community_backend/urls.py` (blog-posts
  URL block, same neighborhood as the `popular`/`featured`/`recent`/etc.
  manual `path()` entries added in todo 307).
- Discovery tag: `web/src/components/PageMeta.tsx`.
- Related: todo 307 (deleted the non-functional JSON stubs this todo
  replaces with a real implementation).

## Acceptance Criteria

- [ ] `GET /blog/rss/` returns valid RSS 2.0 XML (parses with
      `xml.etree.ElementTree` or Django's own feed test client) listing
      recent live+public blog posts.
- [ ] A Django test hits the real URL and asserts the response is valid
      XML with the expected `Content-Type` and at least one `<item>`.
- [ ] Web frontend exposes a discovery `<link rel="alternate">` tag on
      blog pages pointing at the feed.

## Work Log

### 2026-08-30 - Filed

- Filed as a direct follow-up while completing todo 307, at the user's
  request, immediately after todo 307 deleted the non-functional
  `rss`/`atom` JSON stubs. Not urgent — no current consumer — hence p3.

## Notes

- p3: nice-to-have SEO/subscriber feature, no current consumer, no
  security/data risk.
- Do not resurrect the deleted `BlogFeedViewSet.rss`/`.atom` methods —
  they were JSON stubs on the wrong endpoint shape (DRF `@action`, not a
  real syndication `Feed`). Build fresh using `django.contrib.syndication`
  per the forum's proven pattern instead.
