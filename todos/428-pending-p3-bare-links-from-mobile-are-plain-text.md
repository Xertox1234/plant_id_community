---
status: pending
priority: p3
issue_id: "428"
tags: [forum, mobile, backend]
dependencies: []
---

# A plain link posted from the app is neither tappable nor previewed

## Problem

On 2026-09-24, in build 14, the owner posted an ordinary (non-video) link
from the app. It showed as plain text: not tappable, no preview. A video
link alone converts to a card (todo 421), but other URLs get nothing.

## Findings

- **Web:** the composer's TipTap `Link` extension
  (`web/src/components/forum/TipTapEditor.tsx:219`) keeps its default
  `autolink: true`, so a URL typed in the web composer is stored as
  `<a href>`. Readers on web and mobile then get a real link.
- **Mobile:** the composer only makes a link from the `[text](url)` marker
  grammar (`forum_rich_text_markup.dart`). A pasted URL is stored as plain
  text. `ForumHtmlText` makes only `<a>` elements tappable, so readers on
  every client see dead text.
- **Server:** `sanitize_rich_text` doesn't auto-link. The same rule gap as
  todo 421: web-only behaviour that other clients never get.
- **"No preview"** is a separate thing. No client shows preview cards for
  ordinary links. Only YouTube and Vimeo become cards (todo 344). A general
  preview (Open Graph unfurl) would be a new feature: fetching arbitrary
  URLs from the server is an SSRF surface, and it needs caching and a
  timeout like `embeds.py`. Not proposed here.

## Recommended Action

Auto-link on the server, like todo 421. In `validate_forum_body`, after
the 421 conversion, wrap each bare `http(s)` URL in a paragraph's text in
`<a href>`, leaving text already inside `<a>` or `<code>` alone. The
existing sanitizer's scheme allowlist still applies. Every client then gets
a tappable link, and todo 424's launcher opens it.

A client-side alternative (auto-link in `generateForumRichHtml`) is
smaller, but it would repeat the 421 mistake of per-client rules.

Decide separately whether link preview cards are wanted at all.

## Acceptance Criteria

- [ ] A bare `https://` URL in a paragraph posted through the API is stored
      inside `<a href>`, covered by a test that fails first. Prose around it
      is kept.
- [ ] URLs already inside `<a>` or `<code>`, and non-http(s) text, are
      untouched. Pinned by tests.
- [ ] A URL-only video paragraph still becomes an embed (todo 421 wins).
- [ ] On a device: a plain link posted from the app is tappable and opens in
      the in-app browser.

## Work Log

### 2026-09-24 - Filed from build 14's device check
