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

**Owner decisions (all made 2026-09-24):**

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
- **Preview images: DECIDED 2026-09-24 (owner). Never hotlink; cache the
  image.** A reader's device must never contact the linked site. At write
  time the server downloads the `og:image` once and stores its own copy, and
  the card points only at that copy.
  - **Fetch** through the same SSRF-hardened path as the page: the
    `_target_for_url` public-IP pinning plus `_open_connection` in
    `forum_host/link_preview.py`. Add an image read with its own byte cap
    (e.g. 2 MB), the same timeout, and at most 3 redirects.
  - **Validate** like an upload (`backend/docs/patterns/security/file-upload.md`,
    `wagtail_forum/api/upload_validation.py::validate_image_upload`): check
    the content type, then that PIL can decode it, then its pixel dimensions.
    **Re-encode** it (to WebP or JPEG), which strips EXIF and anything else
    embedded, and store it under a size bound.
  - **Store** it through the default storage (R2 in production, local media
    in dev), under a key from a hash of the source image URL, so the same
    image shared by many posts is stored once. Store it as a plain file, not
    a Wagtail `Image` in the forum collection: members can pick from that
    collection, and it has upload-owner rules these files shouldn't join.
  - **Failure** (unreachable, too big, not an image, or undecodable) gives
    a card without an image, not a broken one.
  - **Cleanup: DECIDED 2026-09-24 (owner): add the cleanup job.** A new
    host management command, for example `prune_link_preview_images` in
    `apps/forum_host/management/commands/`, deletes cached preview images
    that nothing refers to. The rules that make it safe:
    - **A reference is any body that can still be shown**, not just live
      posts: `Post.body` AND every Wagtail revision of a post
      (`RevisionMixin`). A post waiting for moderation exists only as a
      revision (todos 422/423), and the edit-history sheet shows old
      revisions, so an image used only there must survive.
    - **Grace period:** never delete a file younger than e.g. 24 h. A post
      being saved right now can hold an image nothing refers to yet.
    - **List the storage prefix, then subtract the referenced set.** Never
      delete by guessing from post rows. Log each deletion with a bracketed
      prefix (`[PRUNE]`), and add `--dry-run`.
    - **Schedule:** run it from the existing nightly `forum-prune-cron`
      (03:00 UTC). Its start command in `.railway/railway.ts` becomes
      `python manage.py prune_forum_tombstones && python manage.py
      prune_link_preview_images`. **Merging a `.railway/` change is a
      production IaC apply** (`railway-apply.yml`), and auto mode blocks it,
      so the owner merges it. After merging, confirm the next 03:00 run logs
      both commands. The cron needs the same `USE_R2`/`R2_*` variables as
      the web service; it already has them, per todo 305.
- **How many cards: DECIDED 2026-09-24 (owner).** One card per link, capped
  at **5 per post**. Links past the cap stay tappable links. Counted
  separately from the existing 5-video `MAX_EMBED_URLS_PER_BODY` cap.
  The owner confirmed this: 5 link cards, separate from the 5 videos.

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
- [ ] A preview image is downloaded once at write time, validated,
      re-encoded and served from our storage. No card on either client
      references a third-party image host. Pinned by a test asserting the
      stored `image_url` is on our media origin.
- [ ] More than 5 standalone links in one post: the first 5 become cards and
      the rest stay tappable links. Pinned by a test.
- [ ] `prune_link_preview_images` deletes only unreferenced cached images
      older than the grace period, and keeps one referenced only by a
      pending or historical revision. Pinned by tests. It runs nightly from
      `forum-prune-cron`, and its first production run is confirmed in the
      cron logs.
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
  on long-press (mobile), and through a screen-reader action. The owner then
  decided that images are cached on our storage and never hotlinked, and
  that there is one card per link, capped at 5 per post. All decisions are
  made; the todo is ready to build.
- The owner asked for the image cleanup job (now part of this todo) and
  confirmed the 5-card cap is separate from videos. A better layout for many
  cards or videos in one post, instead of a vertical stack, is todo 429.
