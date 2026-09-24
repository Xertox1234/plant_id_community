---
status: completed
priority: p3
issue_id: "421"
tags: [forum, mobile, backend, embeds]
dependencies: []
---

# A video link posted from the mobile app never becomes an embed card

## Problem

Todo 344 made YouTube and Vimeo links show as embed cards. The conversion
happens only in the web composer. A link posted from the Flutter app is saved
as a plain paragraph, so readers on every client see a bare link.

Found on 2026-09-24 during build 13's VoiceOver check (todo 398). The owner
posted `https://youtu.be/d2Xc8uupb9E?si=…` alone in a new topic from the app.
Once published, post 289 (topic 44) had one `paragraph` block holding that
URL, and no `embed` block. The app and the web both showed a plain link.

## Findings

- **Web:** `web/src/utils/forumBody.ts:105-121` (`PROVIDER_VIDEO_URL`,
  `embedUrlOf`) turns a paragraph whose only content is a provider URL into an
  `{type: 'embed', value: url}` block when the post is submitted.
- **Mobile:** `buildParagraphBody` in
  `plant_community_mobile/lib/features/forum/models/forum_body_block.dart`
  puts the whole composer input into one `paragraph` block. It has no
  conversion step.
- **Server:** accepts an `embed` block and checks it against
  `WAGTAILEMBEDS_FINDERS` (`wagtail_forum/embeds.py`). It never converts a
  paragraph itself. `grep -iE 'unfurl|auto.?embed|bare.?(url|link)'` over the
  package finds nothing outside the tests.
- So the rule "a URL-only paragraph becomes an embed" lives in one client. Any
  client that doesn't copy it, including a future one, loses the feature
  without any error.

## Recommended Action

Move the conversion to the server so that every client gets it. In the post
create and edit write path, replace a `paragraph` block whose sanitized text is
only a provider URL with an `embed` block. Use the same finder allowlist and
honour `FORUM_EMBEDS_ENABLED`: when it is `False`, the paragraph stays a
paragraph. After that, the web conversion is redundant. It can stay (it does
no harm), or it can be removed so there is a single implementation.

The other option is to copy the regex into `buildParagraphBody`. That is a
smaller change, but it creates a second copy that can drift from the web one,
so it is not preferred.

## Acceptance Criteria

- [x] A post created through the API with a body of one paragraph holding only
      `https://youtu.be/<id>` (with and without a `?si=` query) is stored with
      an `embed` block. Covered by a test that fails before the change.
      `test_embed_autoconvert.py`: 10 tests failed first, each a stored
      `paragraph` where `embed` was expected.
- [x] A paragraph that has a video link inside other prose stays a paragraph.
      This matches the web rule and is pinned by a test.
- [x] A non-provider URL stays a paragraph. With `FORUM_EMBEDS_ENABLED=False`,
      a provider URL also stays a paragraph.
- [x] Editing a post goes through the same conversion. Replies do too.
- [x] On a device: a video link posted from the app shows as an embed card.
      Build 14, 2026-09-24 (owner).

## Work Log

### 2026-09-24 - Filed during build 13's device check

- Reproduced on production: topic 44, post 289.

### 2026-09-24 - Server-side conversion in `validate_forum_body`

- `wagtail_forum/api/sanitize.py`: `_convert_video_paragraphs` runs inside
  `validate_forum_body`, the single body seam that `TopicCreateSerializer`,
  `ReplyCreateSerializer` and `PostEditSerializer` all inherit through
  `_ForumBodyContract`. It runs only when `ALLOW_EMBED_BLOCKS` is on, and
  before the embed checks, so a converted block is allowlisted, capped and
  warmed like an explicit one.
- **Predicate.** `_sole_video_url` reads the paragraph's sanitized text,
  treating every tag as a space and decoding entities. It passes only if
  that text is one whitespace-free token that `is_supported_url` accepts.
  The allowlist is the host's finders, not a copy of the web regex. The
  mobile composer sends no `<p>` (`generateForumRichHtml` joins lines with
  `<br>`). Treating tags as spaces stops `url<br>url` from gluing into one
  bogus URL.
- **Cap.** Conversion stops at `MAX_EMBED_URLS_PER_BODY` distinct URLs,
  counting explicit embeds first, and leaves any further link as a paragraph.
  A body of bare links saved fine before this change, so it must not start
  returning 400.
- **Mutation checks.** Removing the flag gate fails 1 test, removing the
  tag-to-space rule fails 2, and removing the cap check fails 1.
- **Limitation (by design, matches the AC).** On mobile, `Look at this` and
  a URL on the next line form ONE paragraph block (`text<br>url`), so it
  stays a link. On the web the same input becomes two `<p>` elements and
  gets a card. Splitting a block on `<br>` is a separate change.
- **Spam screening.** `spam/base.py::extract_text` flattens an `embed` block
  with `str(EmbedValue)`, which is Wagtail's `embed_to_frontend_html` → provider
  iframe HTML via `get_embed`. So the heuristic still counts about one URL per
  video; the link-count rule doesn't change. But on a cache miss (a warm-up
  that timed out) this refetches the provider inside the request. That was
  already true for explicit embeds from the web (todo 344). This change sends
  more posts down that path, so it is filed as todo 426 rather than changed
  here.
- **Mobile edit (review finding, fixed here).** A link-only mobile post used
  to reopen in the edit screen pre-filled, because it was one plain
  paragraph. Once stored as one `embed` block, it opened blank with the
  "non-text content" warning. `ForumComposeArgs.edit` now pre-fills a lone
  `EmbedBlock` with its URL, escaped like any other text so it round-trips.
  Saving converts it back on the server. There are 3 widget tests; the two
  that pre-fill failed first (`Actual: ''`).
- The web conversion (`forumBody.ts`) stays. It is now redundant but does no
  harm.
- Todo 421 stays `pending` until the build 14 device check (the last AC).

### 2026-09-24 - Verified on a device (TestFlight build 14)

- The owner posted a video link from the app in build 14. After approval it
  showed as a video card. The server conversion shipped in PR #809 and has
  been live since the 16:11 UTC deploy.
- The Edit pre-fill wasn't part of this check. It is pinned by widget tests.
- The same check found that an ordinary (non-video) link posted from the app
  stays plain, untappable text: todo 428.
