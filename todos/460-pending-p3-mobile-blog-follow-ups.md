---
status: pending
priority: p3
issue_id: "460"
tags: [mobile, flutter, blog, follow-up]
dependencies: []
source_review: "todos/archive/385-completed-p3-mobile-blog-and-diagnose-missing.md"
---

# Mobile blog: non-blocking follow-ups from the PR #856 review

## Problem

Round 1 of the PR #856 review (todo 385) found one blocking bug, fixed in
the PR: "Load more" sent the de-duplicated length as the offset. The
non-blocking findings are listed here instead of a third review round.

## Findings

Paths are under `plant_community_mobile/lib/features/blog/`.

- **Pull to refresh** (`screens/blog_list_screen.dart`): `onRefresh` returns
  `ref.invalidate(...)` at once, so the spinner closes before the data
  arrives. Await `ref.refresh(blogPostsProvider(tag).future)` instead.
- **`loadMore` after dispose** (`providers/blog_providers.dart`): nothing
  checks `ref.mounted` after the await. A refresh or leaving the screen
  mid-load can throw `UnmountedRefException`, which the button reports as
  "Could not load more." The forum's `BoardTopics.loadMore` has the same
  shape.
- **Rich text is Wagtail's stored format.** The API sends `db_html`
  (`APIRichText`), so:
  - an internal link is `<a linktype="page" id="N">` with no `href`, and is
    inert;
  - an inline image is a text-less `<embed embedtype="image">`, and is
    dropped;
  - `h2`–`h4` inside a paragraph block run into the text around them, because
    `ForumHtmlText` only breaks on `p`, `br` and `li`.

  The web renders the same payload. Options: expand the rich text on the
  server (`WAGTAILAPI_RICH_TEXT_FORMAT` or a serializer override, which also
  changes the web), or teach the mobile renderer headings and embeds.
- **Self-links and titles** (`screens/blog_post_screen.dart`): an in-body link
  to the post's own slug pushes a duplicate screen. The internal push passes
  no `extra`, so the title bar is blank until the post loads. The
  `/blog/([\w-]+)` regex misses unicode slugs, which Wagtail allows by
  default.
- **Spotlight** (`widgets/blog_block_view.dart`):
  - a failed image leaves an empty 2:1 box;
  - the credit's tap target is about 16 px tall;
  - the web also links "Unsplash" (todo 438), and mobile does not.
- **Naming:** the Home card says "Plant Journal" and the list's app bar says
  "Blog". Pick one.
- **Test gaps:**
  - the Retry button is never tapped;
  - there is no test of internal `/blog/<slug>` navigation;
  - the routing test never pops back from a post;
  - the failed-load test relies on `pumpAndSettle` running through about 40 s
    of fake-clock retries.

## Acceptance Criteria

- [ ] Pull to refresh waits for the reload.
- [ ] `loadMore` is safe after the provider is disposed.
- [ ] A decision on rich-text format, and headings, internal links and
      inline images render (or are recorded as out of scope with a reason).
- [ ] Self-link, title and unicode-slug handling in `_openLink`.
- [ ] Spotlight image failure, credit tap target, and the Unsplash link.
- [ ] One name for the blog on mobile.
- [ ] The test gaps above are covered.
