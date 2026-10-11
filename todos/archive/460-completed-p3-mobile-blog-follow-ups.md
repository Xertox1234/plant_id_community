---
status: completed
priority: p3
issue_id: "460"
tags: [mobile, flutter, blog, follow-up]
dependencies: []
source_review: "todos/archive/385-completed-p3-mobile-blog-and-diagnose-missing.md"
triage: ready
triaged: 2026-10-10
blocked_on: "Choice of rich-text approach (server-side expansion vs mobile renderer vs out of scope) and a single blog name."
owner_decision: "linktype=page links: resolve the id via /api/v2/pages/N/ at tap time; open in-app if a blog post, else its web URL (2026-10-10)"
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

- [x] Pull to refresh waits for the reload.
- [x] `loadMore` is safe after the provider is disposed.
- [x] A decision on rich-text format, and headings, internal links and
      inline images render (or are recorded as out of scope with a reason).
- [x] Self-link, title and unicode-slug handling in `_openLink`.
- [x] Spotlight image failure, credit tap target, and the Unsplash link.
- [x] One name for the blog on mobile.
- [x] The test gaps above are covered.

## Work Log

### 2026-10-10 - Implemented by the todo sweep (run 2026-10-11-0053)

- Rich-text decision: keep Wagtail's stored format (expanding it on the server would change the web's payload too) and teach the mobile renderer. `ForumHtmlText` now breaks `h2`–`h4` into their own blocks, wires `<a linktype="page" id="N">` to a new `onOpenPage` callback, and builds `<embed embedtype="image" id="N">` through `inlineImageBuilder`. The blog wraps it as `BlogRichText`: a page link is resolved at tap time through `/api/v2/pages/N/` (owner decision 2026-10-10), opening a `blog.BlogPostPage` in the app and any other page at its `html_url`; an inline image is looked up once through `/api/v2/images/N/` (`blogInlineImageUrlProvider`, cached per id) and takes no room while loading or when unresolvable.
- `BlogPostScreen`: `/blog/<slug>` is read from the parsed path (`internalBlogSlug`), so raw and percent-encoded unicode slugs match; a link to the post itself pushes nothing; a page link pushes with the page's title as `extra`, and with no title the bar says "Plant Journal" instead of staying blank.
- Pull to refresh awaits `ref.refresh(blogPostsProvider(tag).future)` and swallows its error (the error state shows it). `loadMore` drops a late page after a refresh or a dispose: Riverpod 3.2.1 keeps the ref mounted across a refresh, so `ref.mounted` alone missed that case and the late page was appended to the new feed with a stale offset; a per-build counter catches it. Same guard on the forum's `BoardTopics.loadMore`.
- Spotlight: the 2:1 frame wraps only the loaded image and its placeholder, so a failed image takes no room; credit links are 48 px tap targets; an Unsplash credit (`credit_lead` / `unsplash_href`, now on the mobile model) links the photographer and Unsplash separately, as the web does. One name: `blogDisplayName = 'Plant Journal'` on the Home card, the list's app bar and a post's fallback title.
- Tests: Retry tapped on the list and on a post, internal `/blog/<slug>` navigation and Back (minimal router in `blog_screens_test.dart`, and Back from a post through the production router in `navigation_shell_test.dart`), a 4xx failed load that fails at once with no fake-clock retries, plus the cases above. The older generic-error "a failed load offers Retry" test is unchanged and still runs through the retries. Mutation-checked: the old `onRefresh`, removing the self-link check, and either half of the `loadMore` guard each fail a new test.

### 2026-10-10 - Verified by the todo sweep (run 2026-10-11-0053)

- AC 1: `bash -c 'cd plant_community_mobile && flutter test --no-pub -r expanded test/features/blog/blog_screens_test.dart --name "pull to refresh keeps spinning|a refresh that fails does not throw"'` — evidence `.sweep-evidence/g5/460-ac0.txt` (not committed), last lines:

  ```text
  00:00 +0: todo 460 pull to refresh keeps spinning until the reload is back
  00:00 +1: todo 460 a refresh that fails does not throw out of the indicator
  00:00 +2: All tests passed!

  [exit 0]
  ```

- AC 2: `bash -c 'cd plant_community_mobile && flutter test --no-pub -r expanded test/features/blog/blog_screens_test.dart --name "a page that lands after a refresh|loadMore after the feed is disposed"'` — evidence `.sweep-evidence/g5/460-ac1.txt` (not committed), last lines:

  ```text
  00:00 +0: todo 460 a page that lands after a refresh is dropped, not appended to the new feed
  00:00 +1: todo 460 loadMore after the feed is disposed neither throws nor reports a failure
  00:00 +2: All tests passed!

  [exit 0]
  ```

- AC 3: `bash -c 'grep -n "todo 460 decision" -A6 plant_community_mobile/lib/features/blog/widgets/blog_block_view.dart && cd plant_community_mobile && flutter test --no-pub -r expanded test/features/blog/blog_screens_test.dart --name "headings inside|internal page link|inline image embed|unresolvable page link"'` — evidence `.sweep-evidence/g5/460-ac2.txt` (not committed), last lines:

  ```text
  00:00 +3: todo 460 headings inside a paragraph block start their own line
  00:00 +4: todo 460 an inline image embed is looked up by id and shown
  00:00 +5: All tests passed!

  [exit 0]
  ```

- AC 4: `bash -c 'cd plant_community_mobile && flutter test --no-pub -r expanded test/features/blog/blog_screens_test.dart --name "link to the post itself|unicode slug|internal page link to a blog post|link opens that post, and Back"'` — evidence `.sweep-evidence/g5/460-ac3.txt` (not committed), last lines:

  ```text
  00:00 +2: todo 460 a unicode slug opens in the app, not the browser
  00:00 +3: todo 460 an internal page link to a blog post opens it in the app with its title in the bar before the post loads
  00:00 +4: All tests passed!

  [exit 0]
  ```

- AC 5: `bash -c 'cd plant_community_mobile && flutter test --no-pub -r expanded test/features/blog/blog_screens_test.dart --name "spotlight"'` — evidence `.sweep-evidence/g5/460-ac4.txt` (not committed), last lines:

  ```text
  00:00 +2: todo 460 spotlight each credit link is a full-size tap target
  00:00 +3: todo 460 spotlight a photo that fails to load leaves no empty 2:1 box
  00:00 +4: All tests passed!

  [exit 0]
  ```

- AC 6: `bash -c 'grep -rn "blogDisplayName" plant_community_mobile/lib && cd plant_community_mobile && flutter test --no-pub -r expanded test/features/blog/blog_screens_test.dart test/routing/navigation_shell_test.dart --name "Plant Journal"'` — evidence `.sweep-evidence/g5/460-ac5.txt` (not committed), last lines:

  ```text
  00:00 +0: plant_community_mobile/test/features/blog/blog_screens_test.dart: todo 460 the list is called "Plant Journal", like the Home card
  00:01 +1: plant_community_mobile/test/routing/navigation_shell_test.dart: the blog is reachable from Home (todo 385) Home -> Plant Journal -> a post, keeping the nav bar and a way back
  00:01 +2: All tests passed!

  [exit 0]
  ```

- AC 7: `bash -c 'cd plant_community_mobile && flutter test --no-pub -r expanded test/features/blog/blog_screens_test.dart test/routing/navigation_shell_test.dart'` — evidence `.sweep-evidence/g5/460-ac6.txt` (not committed), last lines:

  ```text
  00:02 +43: plant_community_mobile/test/routing/navigation_shell_test.dart: the Identify FAB does not sit on the nav bar the Identify FAB never covers a tab selection indicator @390pt
  00:02 +44: plant_community_mobile/test/routing/navigation_shell_test.dart: the Identify FAB does not sit on the nav bar the Identify FAB never covers a tab selection indicator @428pt
  00:02 +45: All tests passed!

  [exit 0]
  ```

### 2026-10-10 - Completed by the todo sweep (run 2026-10-11-0053)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
