---
status: pending
priority: p2
issue_id: "428"
tags: [forum, mobile, web, backend, link-preview]
dependencies: []
---

# A pasted link's preview is shown while composing, then thrown away

## Problem

The owner's intent: **a link posted on its own becomes a visual preview card
that replaces the URL entirely.** Every reader, on web and mobile, sees the
card (image, title, description, site) and no URL. Tapping the card opens
the link.

What happens today (found 2026-09-24, build 14 and the web):

- **The web composer** shows exactly that card while you write. Pasting a
  link calls `GET /forum/link-preview/?url=` and renders `LinkPreviewCard`
  under the editor (PR #709, 2026-09-07). But the card is **never saved**:
  the post body holds only the link, and nothing renders a card when the post
  is read. Readers see a bare URL.
- **The mobile composer** has no preview (no reference to `link-preview` in
  `plant_community_mobile/lib`). A pasted link is stored as plain text, which
  is not even tappable, because the app's composer never auto-links (the web
  composer's TipTap `Link` does, with its default `autolink: true`).

So the preview is built and it works; it just isn't used where it matters.

## Findings

- **The fetcher is already SSRF-hardened** and lives in the host:
  `backend/apps/forum_host/link_preview.py::fetch_link_preview(url)`. It
  resolves DNS to public IPs only and pins the connection to that address.
  It allows ports 80/443 and at most 3 redirects, with a 4 s timeout and a
  512 KB body cap. It parses only OG, Twitter, `<title>` and
  `description`, and it caches results for 1 h (failures for 60 s). It
  returns `{url, title, description, image_url, site_name, domain,
  available}`. The endpoint is throttled at 30/min.
- **Package/host boundary.** Post bodies are validated in the package
  (`wagtail_forum/api/sanitize.py::validate_forum_body`), but the fetcher is
  in the host app. The package must not import `apps.forum_host`. That needs
  a host hook setting, the same shape as `WAGTAILFORUM_SPAM_BACKEND`, for
  example `WAGTAILFORUM_LINK_PREVIEW_FETCHER` (a dotted path). If it isn't
  set, nothing converts.
- **The precedent is todo 421 plus todo 344 (video embeds).** A URL-only
  paragraph is converted on the server at write time, the provider is
  contacted once under a bound, and reads never fetch. The same posture
  applies here.
- **A new StreamField block is four changes** (`docs/rules/wagtail.md`): the
  block plus its migration (the block list is schema), a serializer branch, a
  renderer on the web AND a model plus widget on Flutter, and a README
  contract entry.

## Recommended Action

1. **A `link_preview` body block** holding a **snapshot** taken at write
   time: `{url, title, description, image_url, site_name, domain}`. Unlike
   video embeds there is no Wagtail cache table to read from, so the data is
   stored in the block. A read never fetches, and the card doesn't change if
   the page later does.
2. **Server conversion in `validate_forum_body`, after the 421 video
   conversion.** A paragraph whose only content is one `http(s)` URL (the
   same text test as `_sole_video_url`, minus the finder allowlist) and that
   is not a video becomes a `link_preview` block. The data comes from the
   host fetcher. If the fetch returns `available: false`, times out, or no
   fetcher is configured, it stays a paragraph, auto-linked (see 5). Every
   client gets the card, including mobile, whose composer can't build
   blocks.
3. **Readers: a card, no URL.** Web: reuse `LinkPreviewCard` in the post
   renderer. Flutter: a `LinkPreviewBlock` model and a card widget, tappable
   through the existing `onOpenLink` (todo 424 opens it in the in-app
   browser), with a semantics label such as `"Link: {title}, {site}"` and a tap
   action (the lesson from todo 398).
4. **The mobile composer shows the same card while writing**, calling the
   existing endpoint, for parity with the web. It's optional for the first
   slice, because the server conversion already delivers the card to readers.
5. **Links inside prose** stay links and don't become cards. They must at
   least be tappable, so the server auto-links bare `http(s)` URLs in
   paragraph text (skipping text already inside `<a>` or `<code>`). That was
   this todo's original proposal, and it is still needed for the prose case.

**Decisions for the owner before building:**

- **The address line: DECIDED 2026-09-24 (owner).** The card shows a
  **shortened URL**, never the full one: the origin, with an ellipsis when
  there's a path. For example `https://microsoft.com/…` for
  `https://microsoft.com/en-us/windows/some/long/path?x=1`. The full URL is
  still reachable:
  - **Web:** the card's `title` attribute carries the full URL, so hovering
    shows it (`alt` applies only to images). The browser status bar also
    shows the link target on hover.
  - **Mobile:** there is no hover, so **long-press** shows the full URL.
    Flutter's `Tooltip` already triggers on long-press. Include a "Copy link"
    action there.
  - **Screen readers:** the spoken label is the title plus the shortened
    address, never the full URL. VoiceOver spells a URL out character by
    character, which is the build 13 bug from todo 424. The full URL is
    offered as a custom semantics action ("Show full address"), which a
    VoiceOver user can reach without a long-press.
- **Preview images.** `image_url` points at the third-party site, so showing
  it means every reader's device fetches from that host. That leaks the IP
  and lets the site track who read the post. Options: hotlink it (simplest,
  and the composer does this today), or copy the image into our storage (R2)
  at write time (private, but more work and needs its own size and type
  checks). Recommended: copy the image, or ship without images first.
- **Several links on their own lines:** a card each, capped the way videos
  are (`MAX_EMBED_URLS_PER_BODY`, or a separate cap).

## Acceptance Criteria

- [ ] A post whose body is only a non-video URL is stored as a
      `link_preview` block with the fetched snapshot. Covered by a test that
      fails first, with the fetcher faked (no network in tests).
- [ ] A failed or unavailable fetch, or no configured fetcher, leaves a
      tappable link (a paragraph holding `<a href>`), not a card and not
      plain text.
- [ ] A video URL still becomes an `embed` (todo 421 wins), and a link inside
      prose stays in the prose as a link.
- [ ] Reading a post never contacts the linked site. Pinned by a test that
      patches the fetcher to raise.
- [ ] Web and mobile render the card with the shortened URL (origin plus
      `…`) and never the full one, and open the link on tap. Pinned by tests.
- [ ] The full URL is reachable: web `title` (hover), mobile long-press, and
      a screen-reader custom action. The spoken label never contains the
      full URL. Pinned by widget and Vitest tests.
- [ ] Every "new block" change is present: the migration, the serializer
      branch, the web renderer, the Flutter model and widget, and the README.
- [ ] On a device: a link pasted in the app composer shows as a preview card
      for readers on both platforms.

## Work Log

### 2026-09-24 - Filed from build 14's device check; rescoped by the owner

- First filed as "auto-link bare URLs on the server". The owner rejected
  that: "When I paste the link I get a preview of the link. that preview is
  suppose to replace the link entirely when viewing the post. Anyone who sees
  this post should see a visual preview of the link and no URL at all" and
  "the preview is already in the posting interface... it is just not being
  used". Rescoped to persisting and rendering the preview. Auto-linking stays
  only for links inside prose.
- The owner decided the address line: show a shortened URL
  (`https://microsoft.com/…`) with the full URL available on hover (web),
  on long-press (mobile), and through a screen-reader action. Still open:
  preview images (hotlink or copy) and the cap on the number of cards.
