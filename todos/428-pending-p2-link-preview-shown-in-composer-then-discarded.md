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

### 2026-09-25 - Slice A (backend core) built; the host fetcher stays UNSET

- **Package (`wagtail_forum`):**
  - The `link_preview` block (`LinkPreviewBlock`: `url`, `title`, `description`,
    `image`, `site_name`, `domain`), plus migration 0039.
  - The `WAGTAILFORUM_LINK_PREVIEW_FETCHER` hook, `fetcher(url) -> dict | None`,
    with its own timeout, cap and image-prefix settings.
  - Conversion in `validate_forum_body`. It runs after everything that can
    return a 400, so a body that is refused costs no fetch, and before the
    `to_python` dry-run.
  - `link_previews.py`: concurrent fetches in one window, the stored-card
    reuse on edit, and the read envelope.
  - Auto-linking of bare URLs in every paragraph.
  - The serializer branch and the README "Link previews" section.
- **Host:** `apps/forum_host/link_preview.py::link_preview_snapshot` adapts
  `fetch_link_preview` to the hook. It answers `None` for "no card", and its
  `image` is always blank until slice B caches our own copy.
- **Decisions made while building, not in the owner's list:**
  - **A submitted card keeps only its URL.** Its other fields come from the
    stored body (the edit reuse) or from the fetcher, so no member can forge a
    card's title or image.
  - **A video URL is never a card while embeds are on**, so the caps stay
    separate. A 6th video stays a link.
  - **The first 5 distinct candidates are fetched; later ones never are.** A
    failed fetch does not give its slot to link #6.
  - **Heuristic spam check:** it counted `https?://` in raw markup, so an
    auto-linked `<a href="X">X</a>` counted twice. Two links in a post would
    have read as four against `SPAM_MAX_LINKS=3`. `extract_text` now
    collapses a link whose text equals its href. A link hiding its address
    (`<a href="spam">click</a>`) still counts. Web posts (TipTap autolinks)
    already had this double count before this change.
  - **Spam and mentions read the card's URL**, never the fetched title or
    description.
- **Why the setting stays unset (slice C gate).** Today the web editor's
  `bodyBlocksToHtml` returns `''` for an unknown block type, so the first
  web edit of a post holding a card would silently drop the link. The
  mobile `ForumComposeArgs.edit` would send a single-card post to the
  `hasNonTextContent` warning. Slice C must therefore add, beside the
  renderers:
  - web `bodyBlocksToHtml`: `link_preview` becomes `<p><a href=url>url</a></p>`
    (the same as the embed branch);
  - mobile: a single `LinkPreviewBlock` offers its URL (the same as the
    `EmbedBlock` branch);

  and only then set `WAGTAILFORUM_LINK_PREVIEW_FETCHER =
  "apps.forum_host.link_preview.link_preview_snapshot"` in host settings.
  The server re-derives the same card from the stored one on save, with no
  fetch.
- **Live in slice A:** auto-linking only. New mobile posts now store `<a>` for
  bare URLs.
- **Mutation checks: 22 of 22 caught**, each restored from a `cp` backup and
  confirmed with `cmp`:
  - cap;
  - linked-paragraph fallback;
  - read never fetches;
  - client fields ignored;
  - edit reuse;
  - video wins;
  - card-URL gate;
  - fetch only after validation;
  - write-side and read-side image vetting;
  - read-side URL vetting;
  - timeout window;
  - fetcher raises;
  - a dotted path that does not import;
  - spam self-link collapse, hidden href still counted, card counted by URL;
  - auto-link skipping `<a>`/`<code>`, trailing-punctuation trim, and the
    host check;
  - host adapter: no hotlinked image, unavailable page.
- **A test flake fixed in development:** the timeout test's fetcher finished
  late and recorded a call into a later test. That cause is a hypothesis
  from the timing; I could not reproduce the failure on demand. The fetcher
  now blocks on an event that the test releases.
- **Review round 1 found no blocking issue** (bundled `/code-review` and
  `code-review-orchestrator`), so no round 2 was needed. The seven
  non-blocking findings are in **todo 448**. Its items 1–3 (fetch-queue
  backlog, a sole `<code>` URL becoming a card, `URLBlock` rejecting hosts
  that `is_card_url` accepts) are a **gate for slice C**: fix them before
  the host setting is turned on.
- **Full backend suite: 3865 passed, 8 skipped, 1 failed.** The failure was
  an expected change: a video link past the cap is now stored auto-linked.
  I updated that assertion, and the embed autoconvert file passes (20/20).

### 2026-09-25 - Slice B (preview images) built; the host fetcher stays UNSET

- **Host only** (`apps/forum_host/link_preview.py`); the package is unchanged
  apart from one README sentence giving the exact image-name shape.
  `link_preview_snapshot` now fills `image` with the name of **our** copy of
  the page's og:image, or `""`.
- **Download:** once, at write time, through the same SSRF-pinned path as the
  page (`_target_for_url` + `_open_connection`):
  - HTTPS only, on the first hop and every redirect; each redirect is
    re-validated as a public address; at most 3 redirects;
  - `Content-Type` must be the upload allowlist (`IMAGE_ALLOWED_MIME_TYPES`)
    or `image/jpg`, which CDNs send; a missing type is refused;
  - 2 MB cap, checked on `Content-Length` and while streaming.
- **Validation, then re-encode:** `Image.open(..., formats=JPEG/PNG/GIF/WEBP)`
  (no other decoder sees the bytes); the size from the header is checked
  before decoding: each side at most 4096, and at most 8,388,608 pixels (the
  decompression-bomb guard). Then a full decode (a truncated file fails
  here), EXIF orientation applied, converted to RGB or RGBA, shrunk to at
  most 1200 px, rebuilt from pixels alone and saved as WebP (quality 80).
  Stored bytes carry no EXIF, XMP or ICC.
- **Storage:** plain `default_storage` files (R2 in prod), not Wagtail
  Images, at `forum/link-previews/<sha256 of the image URL>.webp`. Only WebP
  is written; the read pattern also allows `.jpg`, which nothing writes. A
  name that already exists is reused with no download, so a second post with
  the same image costs nothing. If two posts race, R2's
  `file_overwrite=False` gives the second a suffixed name; that copy is
  deleted and the canonical name used.
- **Any image failure gives a card without an image**, never a broken card
  and never a lost card.
- **The time budget (the constants decision).** The page and the image share
  one deadline: the package's `LINK_PREVIEW_FETCH_TIMEOUT_SECONDS` (5 s)
  minus `LINK_PREVIEW_SNAPSHOT_MARGIN_SECONDS` (1 s, left for decoding,
  encoding and the storage write). The deadline is read from the package
  setting, so changing the window moves the budget with it. No download
  starts with less than `LINK_PREVIEW_IMAGE_MIN_SECONDS` (1 s) left. The
  page's own constants (4 s socket timeout, 2 s DNS) are unchanged; the
  composer's preview request usually leaves the page in the 1 h cache, so the
  image typically gets most of the budget.
  - The image deadline is **hard**: DNS is capped at the time left, reads use
    `read1` with a deadline check before each chunk, and a watchdog timer
    shuts the socket down at the deadline. A socket timeout alone bounds each
    `recv`, not the request, so a server dripping one byte at a time kept
    `readline` (status line, headers) alive indefinitely. A loopback test
    drives exactly that.
  - The TLS handshake needs no watchdog: CPython bounds the **whole**
    handshake by the socket timeout (probed: a dripped handshake failed at
    0.31 s with a 0.3 s timeout), and the timeout is capped at the time
    left. A loopback test pins it.
  - Not covered: the page fetch, which still has todo 448 item 5's
    per-`recv` timeout.
- **For slice D:** a fetcher still running when the package's window closes
  keeps going. The post saves the link as a paragraph, but the image may still
  be written, leaving a file nothing references. The prune command's 24 h
  grace and reference check cover it.
- **Tests:** `apps/forum_host/tests/test_link_preview_images.py` (30 tests, no
  network: page previews patched, image connections faked, a loopback server
  for the watchdog, Django's in-memory storage on a media origin of our own).
  One test turns the fetcher on for itself only and posts through the real
  `/api/v1/forum/` mount. It asserts the served `image_url` is
  `MEDIA_URL + forum/link-previews/<sha256>.webp`, never the source host. That
  is the backend half of the "no third-party image host" acceptance criterion;
  the client half is slice C.
- **Mutation checks: 26 of 26 guards caught** on the final code, each run against a `cp`
  backup, restored, and confirmed with `cmp`. The guards: declared and
  streamed size cap, redirect limit, HTTPS-only redirect, SSRF re-check on
  redirect, entry HTTPS check, content type, 2xx status, decode and
  re-encode, format allowlist, bomb (pixels), side limit, EXIF strip, EXIF
  orientation, name pattern, dedupe, read-loop deadline, `read1` vs `read`,
  watchdog, minimum budget, race delete, race canonical-only, and the
  snapshot swallowing an image bug.
  - The streamed cap and the redirect limit are each enforced twice: the
    read size never exceeds limit + 1, and the loop's `range` stops a 4th
    redirect. Removing one half alone is an equivalent mutation, so each was
    checked with both halves removed.
  - Added after review: the TLS/connect timeout cap, the post-loop
    deadline check, and the `Content-Length` shortfall check.
  - Pillow 12's WebP encoder copies no EXIF unless asked, so the pixels-only
    rebuild is defence in depth. The EXIF mutation passes EXIF through
    explicitly, and the test catches it.
- **Review round 1** (bundled `/code-review` + `code-review-orchestrator`):
  - **Fixed (blocking):** a body cut off by the watchdog, or closed before its
    `Content-Length`, read as a normal end of body. Neither raises in
    `http.client`, so the partial bytes went to PIL. PIL rejects most such
    files today, but a half image stored under the URL's hash would be reused
    forever. `_read_image` now refuses both.
  - **False positive, disproved:** "the watchdog starts after the TLS
    handshake, so a dripped certificate chain holds a thread for hours". I
    first built an fd-based watchdog armed before the handshake. Its mutation
    check then survived (arming after `connect` still passed), and the probe
    above showed why: CPython already bounds the whole handshake. I reverted
    to the simpler watchdog and kept the test.
  - **Non-blocking, in todo 448 (item 9):** the snapshot's budget starts when
    a pool thread picks the job up, not when the package starts its 5 s
    window, so a queued job can overrun it.
  - The orchestrator found no blocking issue.
- **Round 2** (targeted check of the fix): the new checks are mutation-pinned
  (in the 26 above), and both host test files pass (54/54).
- **Full backend suite:** 3895 passed, 8 skipped, 0 failed. It ran before the
  round-1 fix; that fix touches only `link_preview.py`, and its two test
  files were rerun.

### 2026-09-26 - Slice C (readers, both edit round trips) built; cards are ON

- **Gate first (todo 448 items 1–3 and 9), package + host:** queued fetches
  are cancelled when the window closes; the fetcher gets `deadline`, the
  window's end counted from submit, and the host budgets the image from it; a
  sole `<code>` URL is never a card; `is_card_url` runs the block's own
  `URLValidator`. Details and the 8/8 mutation result are in todo 448.
- **Turned on:** host settings set `WAGTAILFORUM_LINK_PREVIEW_FETCHER` to
  `apps.forum_host.link_preview.link_preview_snapshot` (`LINK_PREVIEW_FETCHER_PATH`,
  pinned by a test that imports it). Two additions to the owner's brief,
  following the `FORUM_EMBEDS_ENABLED` precedent:
  - `FORUM_LINK_PREVIEWS_ENABLED` (default `True`) is a kill switch: `False`
    leaves links as auto-linked paragraphs and stored cards still render.
  - The setting is always off under test runs (`_IS_TEST_RUN`), so no test
    reaches the network; a test that wants cards overrides it.
- **Web:** `StreamFieldRenderer` renders `link_preview` with `LinkPreviewCard`
  (a new `post` variant); a `null` card renders nothing.
  - Address line: `shortLinkAddress`, the origin plus `/…` when anything
    follows the root (`https://microsoft.com/…`).
  - Full URL: only the `href` and the `title` attribute (hover).
  - Spoken label: `aria-label` is the title plus the short address.
    `aria-describedby` points at a hidden "Opens in a new tab" hint, because
    a link with no description of its own exposes its `title` as the
    accessible description, and a screen reader would read the full URL
    after all. Pinned with `toHaveAccessibleName` and
    `toHaveAccessibleDescription`.
  - Tap: the existing plain `<a target="_blank" rel="noopener noreferrer">`
    (nothing in the post view intercepts link clicks).
  - Image: `mediaUrl(image_url)` (our storage; relative `/media/…` in dev),
    not the composer's https-only rule for third-party images.
  - Edit round trip: `bodyBlocksToHtml` turns `link_preview` into
    `<p><a href=url>url</a></p>`, sharing the embed branch's http(s) guard.
    Saved unchanged, the server re-derives the same stored card, no fetch.
- **Flutter:** `LinkPreviewBlock` (a hand-written sealed-class case like the
  other blocks; no codegen, so no build_runner) and `linkPreviewShortAddress`,
  tested against the same table as the web.
  - The card: image, site, title, description, short address; tap goes to
    `onOpenLink` (the in-app browser, todo 424).
  - Spoken label `Link: {title}, {short address}`, one semantics node.
  - **Deviation from the brief: long-press opens a bottom sheet, not a
    Tooltip.** A Flutter tooltip overlay cannot hold a tappable "Copy
    link". The sheet shows the full address (selectable) and a "Copy link"
    button.
  - Screen readers get "Show full address" (opens the sheet) and "Copy
    link" as custom semantics actions, which VoiceOver offers with no
    gesture.
  - Edit round trip: `ForumComposeArgs.edit` offers the URL of a lone card,
    as it does for a lone video embed.
- **Both platforms:** when the page gave no title, site or domain, the title
  falls back to the short address, and the address line is not repeated.
- **Mutation checks:** web 15 of 15 and Flutter 13 of 13 caught, each against
  a `cp` backup, restored, and confirmed with `cmp`.
  - One Flutter survivor on the first pass, `excludeSemantics: false`. A
    semantics-tree probe showed the real effect: the InkWell adds a second,
    focusable node with tap and long-press but **no label**, an unlabeled
    button. The full URL was never spoken either way. The test now asserts
    the card is one node, and the mutant is caught.
- **Review round 1** (bundled `/code-review` + `code-review-orchestrator`):
  - **Fixed (blocking): the kill switch stripped stored cards on edit.** Both
    reviewers found it. Stored cards were reused only when a fetcher was
    set, so with `FORUM_LINK_PREVIEWS_ENABLED=False` any edit of a post (even
    a typo elsewhere) turned its card back into a paragraph and orphaned its
    image. That contradicted the documented "stored cards still render".
    Reproduced first with a failing test (web, mobile and echoed-block edit
    shapes, 3 of 3 failed), then fixed in `_convert_link_previews`: reuse
    needs no fetch, so it no longer waits for a fetcher.
  - **Fixed (blocking per the orchestrator, low per `/code-review`): a
    relative image URL on mobile.** With local storage,
    `link_preview_envelope` served `/media/…`, which the web resolves with
    `mediaUrl` but Flutter's `CachedNetworkImage` cannot. It now takes the
    request and makes the URL absolute, as `serialize_image_for_api` does
    for image blocks. Production (R2) already served absolute URLs.
  - **Checked and not an issue:** E2E posts reaching real sites (no forum
    E2E spec posts a URL).
  - **Non-blocking, to todo 448:** item 10 (a sole `<code>` video URL still
    becomes an embed, pre-existing) and item 11 (a card-only topic has an
    empty list excerpt). The page fetch's own timeout is item 5 there.
- **Round 2** (targeted check of the fixes): 3 of 3 mutants caught (reuse
  gated on a fetcher, request not passed, URL not made absolute), each
  restored and confirmed with `cmp`.
- **Suites on the final code:** backend 3926 passed, 8 skipped, 0 failed
  (run after the round-1 fixes); web Vitest 1514 of 1514; Flutter forum tests
  529 of 529, `flutter analyze` clean; `tsc --noEmit` clean.
- **Left for later slices:** D (the prune command; the owner merges the
  `.railway/` change) and the on-device check. E (the mobile composer preview)
  stays optional.

### 2026-09-26 - Slice D (prune command) built; the cron change is a separate owner-merged PR

- **`manage.py prune_link_preview_images`** (`apps/forum_host/management/commands/`):
  lists `forum/link-previews/` and reads each file's age, THEN scans every
  `Post.body` (no `live` filter) and every post revision (`base_content_type`,
  the JSON-string body) for any string under the prefix, and deletes old
  unreferenced files. Never a file younger than
  `LINK_PREVIEW_IMAGE_PRUNE_GRACE_HOURS` (24); `--dry-run`; one `[PRUNE]` line
  per deletion plus a summary line that prints even at zero. It refuses a
  blank, root or unterminated prefix, keeps a file whose age can't be read,
  aborts with nothing deleted when a revision body won't parse, and fails the
  run (after trying the rest) when a delete fails. Orphaned suffixed
  duplicates from a concurrent store are reaped too.
- **Residual window, documented, not closed:** the fetcher reuses an existing
  file without touching it, so a post that re-shares an image older than 24 h
  and commits between the reference scan and the delete gets a card without
  an image. Closing it means changing slice B's store path.
- **Deviation from the brief: the cron command is wrapped in `/bin/sh -c`.**
  Railway runs a Dockerfile service's start command in exec form with no shell
  (docs.railway.com/deployments/start-command), so the brief's bare `&&` would
  have reached `manage.py` as an argument and broken the tombstone prune too.
  Same wrapper as Redis's start command in `.railway/railway.ts`. `&&` is kept:
  a failed tombstone prune skips the image prune that night.
- **Merge order:** the command PR first, the `.railway/` PR (owner merges,
  production IaC apply) after the command has deployed.
- **Full backend suite:** 3945 passed, 8 skipped, 0 failed.
- **Tests:** 15 in `apps/forum_host/tests/test_prune_link_preview_images.py`
  (in-memory storage, ages via `freeze_time`, real posts and revisions).
  11 of 11 guard mutants caught, each restored and confirmed with `cmp`.
  A local dry run and real run against the dev DB and disk storage deleted
  only the aged unreferenced file.
- **Review round 1** (bundled `/code-review` + `code-review-orchestrator`): no
  blocking findings. The only actionable note was the merge order above. No
  round-2 fixes to verify.
- **Left:** the owner merges the `.railway/` PR, then the next 03:00 UTC run is
  confirmed to log both commands (the last part of this slice's AC); then the
  on-device check. E stays optional.
