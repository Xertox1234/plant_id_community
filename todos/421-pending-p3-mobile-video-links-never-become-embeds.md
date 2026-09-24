---
status: pending
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

- [ ] A post created through the API with a body of one paragraph holding only
      `https://youtu.be/<id>` (with and without a `?si=` query) is stored with
      an `embed` block. Covered by a test that fails before the change.
- [ ] A paragraph that has a video link inside other prose stays a paragraph.
      This matches the web rule and is pinned by a test.
- [ ] A non-provider URL stays a paragraph. With `FORUM_EMBEDS_ENABLED=False`,
      a provider URL also stays a paragraph.
- [ ] Editing a post goes through the same conversion.
- [ ] On a device: a video link posted from the app shows as an embed card.

## Work Log

### 2026-09-24 - Filed during build 13's device check

- Reproduced on production: topic 44, post 289.
