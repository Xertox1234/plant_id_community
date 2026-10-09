---
status: completed
priority: p2
issue_id: "448"
tags: [forum, backend, link-preview, review-follow-up]
dependencies: ["428"]
owner_decision: "Item 13: set target=_blank server-side in the package sanitizer. Item 11: leave a card-only excerpt empty (2026-09-28)"
---

# Link preview slice A: non-blocking review findings

Filed from todo 428 slice A's review round 1 (bundled `/code-review` plus
`code-review-orchestrator`, 2026-09-25). Neither reviewer found a blocking
issue. Items 1–3 are **latent** while `WAGTAILFORUM_LINK_PREVIEW_FETCHER` is
unset. **Fix them before slice C turns the fetcher on.** Item 4 is live now
but rare.

## Findings

1. **The fetch queue can back up (gate for slice C).**
   - Where: `wagtail_forum/link_previews.py::fetch_snapshots`.
   - Futures still queued when the window closes are never cancelled. The
     pool is 8 threads with an unbounded queue, and one host fetch can
     take well over 5 s (2 s DNS plus 4 s per request, up to 4 requests).
   - A burst of posts with 5 slow links each fills the pool. Later posts'
     fetches then time out before they start, so their links save as plain
     links while the backlog lasts.
   - Fix: `future.cancel()` for pending futures that have not started, and/or
     a bounded submit.
2. **A code sample posted on its own becomes a card (gate for slice C).**
   - Where: `api/sanitize.py::_sole_url`.
   - It strips all markup, so `<p><code>https://api.example.com/v1/x</code></p>`
     counts as a link on its own, is fetched and is replaced by a card. The
     auto-linker deliberately skips `<code>`; the card path should too.
3. **Moderator save can fail on a card (gate for slice C).**
   - Where: the `LinkPreviewBlock.url` field versus `is_card_url`.
   - `is_card_url` accepts hosts that the block's `URLBlock` (Django
     `URLValidator`) rejects, for example `https://my_site.example.com/`. The
     API only runs `to_python`, so such a card saves. After that, a moderator's
     `/cms/` save of the post fails with "Enter a valid URL" on a block they
     never touched.
   - Fix: make `url` a `CharBlock`, or run `URLValidator` inside
     `is_card_url`.
4. **Auto-linking can push a body over `MAX_BODY_CHARS` (live, low).**
   - Where: `api/sanitize.py`. The 100k check runs before auto-linking,
     which adds about 50 characters per bare URL.
   - A body near the limit with many bare URLs stores at more than 100k.
     Resending it unchanged on edit is then refused as "Post body is too
     large".
   - Fix: re-check the size after auto-linking and refuse on create, or check
     the pre-link size on edit.
5. **A slow-dripping origin can hold a pool thread (pre-existing, PR #709).**
   - Where: `apps/forum_host/link_preview.py`. `timeout=4` is per `recv`,
     not a wall clock, so an origin dripping bytes can hold a thread for a
     long time while it reads up to 512 KB.
   - Slice A's bounded pool contains the damage. A wall-clock deadline in
     `_read_document` would remove it.
6. **A stored image name is carried without validation (cosmetic).**
   - Where: `link_preview_snapshots`, which carries the stored `image`
     unchecked. The read envelope gates it, so nothing is served.
   - Validate it there too for symmetry.
7. **A sole link with trailing punctuation (cosmetic).**
   - `https://example.com.` as a paragraph's only content becomes a card
     candidate with the dot kept. `_trim_url` could apply before the card
     check.

8. **`test_spam.py` fails when run on its own (pre-existing).**
   - Where: `test_spam.py`. Its non-DB tests call `get_setting`, and the
     host override provider (`apps/forum_host/forum_settings.py::_load_values`)
     reads the DB whenever its cached values are cold.
   - Run alone with a cold cache, 10 of 14 fail with "Database access not
     allowed". Run after any DB test, they pass. The full suite is unaffected.
   - Fix: give those tests the `db` mark, or stub the provider for non-DB
     tests.
9. **The image budget starts late when the pool is backed up (slice B,
   gate for slice C with item 1).**
   - Where: `apps/forum_host/link_preview.py::link_preview_snapshot`, which
     computes its deadline when the snapshot starts running. The package's
     5 s window starts when the job is submitted.
   - A job that waits 2 s in the 8-thread queue still gets its full 4 s, so
     it ends about 6 s after submit, past the window, and the whole card is
     lost. Any image it stores becomes an orphan for slice D's prune.
   - Fix together with item 1: pass the fetcher a deadline (or the submit
     time). That changes the package's `fetcher(url)` contract, so it is a
     package change.
   - Found by the bundled `/code-review` in todo 428 slice B round 1.

10. **A sole `<code>` video URL still becomes an embed (pre-existing,
    todo 421).**
    - Where: `api/sanitize.py::_sole_video_url`, which calls `_sole_url`
      without `skip_code`. The video conversion runs before the card
      conversion, so `<p><code>https://www.youtube.com/watch?v=x</code></p>`
      becomes an embed, while the same thing with a non-video URL now stays
      code (item 2).
    - The web composer does the same client-side (`embedUrlOf` reads
      `textContent`), so fixing only the server leaves the web converting.
    - Found by the bundled `/code-review` in todo 428 slice C round 1.
11. **A topic whose body is only a card has an empty list excerpt.**
    - Where: `api/views.py::plain_text_excerpt`, which skips dict-valued
      blocks without `code` or `text`, as it already does for a lone video
      embed.
    - The card's title is the linked page's words, not the author's; if an
      excerpt should show something, the short address is the safer choice.
    - Noted during todo 428 slice C.

12. **A failed page fetch logs nothing (found on device, 2026-09-26).**
    - Where: `apps/forum_host/link_preview.py::fetch_link_preview` returns
      `available: False` for a timeout, an HTTP error, a refused redirect or
      a page with no usable title, and none of these is logged. The package
      logs only a fetch still running when its window closes.
    - Why it matters: the owner's device check posted a CBC article and got a
      plain link. Production logs held no `[LINK_PREVIEW]` line, so it took
      local reproduction to find the cause. CBC's bot protection holds a
      request with our User-Agent open without answering (Slack's and
      Discord's bots too; Twitterbot gets a 403), our 4 s timeout fires, and
      the post keeps the link, as designed.
    - Fix: one `[LINK_PREVIEW]` info line per failed fetch naming the reason
      (timeout, HTTP status, redirect refused, no title) and the host, never
      the full URL's query. Pin it with `assertLogs` per reason.
    - Out of scope (owner, 2026-09-26): no browser User-Agent or omitted
      User-Agent to get past a site's bot blocking. A site that refuses
      preview bots stays a plain link.
13. **Plain links in a web post body open in the same tab.**
    - Where: `web/src/components/StreamFieldRenderer.tsx` renders a
      `paragraph` block's sanitized HTML as is, so an auto-linked or written
      `<a>` has no `target`. Link cards open in a new tab
      (`target="_blank"`, `rel="noopener noreferrer"`), so a card and the same
      link as text behave differently. The owner noticed this during the
      device check.
    - Fix: give body links `target="_blank"` with `rel="noopener noreferrer
      nofollow"`, either server-side where the package's sanitizer and
      auto-linker write `<a>` (so the mobile renderer is unaffected; it
      always opens the in-app browser), or in the web renderer. Keep internal
      forum links (mentions, "in topic" quote links) in the same tab. Vitest
      for both kinds.

## Acceptance Criteria

- [x] Items 1–3 and 9 are fixed and pinned by tests (each mutation-checked) before
      the host setting is turned on in todo 428 slice C. (2026-09-26, slice C.)
- [x] Items 4–8 and 10–13 are fixed or closed with a reason. (2026-10-09: 4, 6, 7, 10, 13 in #971; 5, 12 in #972; 8 closed, fixed by #913; 11 closed per the owner's decision.)

## Work Log

### 2026-09-25 - Filed from todo 428 slice A review round 1

- Neither reviewer found a blocking issue, so round 2 was not needed. Findings
  above were copied from both reports and checked against the code.

### 2026-09-26 - Items 1–3 and 9 fixed in todo 428 slice C

- **Item 1:** `fetch_snapshots` calls `future.cancel()` on every future still
  pending when the window closes. A queued fetch is dropped (logged "never
  started"); only one already running gets the late-failure log callback.
- **Item 9:** the fetcher contract is now `fetcher(url, *, deadline)`. The
  package computes `deadline = time.monotonic() + timeout` once, before
  submitting, so every fetch in a body shares the window's real end. The host's
  `link_preview_snapshot` budgets the image as `deadline - margin`. A direct
  call without `deadline` starts its own window, as before.
- **Item 2:** the card path calls `_sole_url(..., skip_code=True)`; any
  non-blank text inside `<code>` means "not a card". The video path is
  unchanged (a sole `<code>` video URL still becomes an embed, on web too).
- **Item 3:** `is_card_url` also runs Django's `URLValidator(schemes=http,
  https)`, the check `URLBlock` runs. No block schema change, no migration.
  A test runs 17 URL shapes through both and fails if `is_card_url` accepts one
  the block's `clean` refuses; an end-to-end test cleans the stored body the
  way a `/cms/` save would.
- **Mutation checks: 8 of 8 caught** (no cancel; deadline from pickup;
  deadline not passed; card path allows code; code flag never set; no
  `URLValidator`; host ignores the deadline; host drops the margin). Each ran
  against a `cp` backup, was restored, and confirmed with `cmp`.
- Items 4–8 are still open. Items 10 and 11 were added from slice C's review.

### 2026-09-26 - Items 12 and 13 added from the todo 428 device check

- The owner asked for both. Item 12 is the diagnosis gap behind the CBC post;
  item 13 is the same-tab behavior the owner saw on the web.

### 2026-10-09 - Items 4, 6, 7, 10 and 13 fixed; 8 and 11 closed (PR 1 of 2)

- **Item 4:** `validate_forum_body` checks the size again on the body it
  returns, after cards and auto-linking. A body is refused when what would be
  STORED passes the cap, so a body that saved always re-saves unchanged.
  Refusing now happens after the card fetch, but only for a body within a few
  hundred characters of 100k.
- **Item 6:** `link_preview_snapshots` keeps a stored image only when
  `is_cached_image_name` accepts it, the same rule as `_snapshot`.
- **Item 7:** the card path runs `_trim_url` on a sole paragraph URL, so
  `https://example.com/a.` cards `https://example.com/a`. The video path is
  unchanged: its provider finders decide what is a video.
- **Item 8: closed, already fixed** by todo 501 (#913, `d12dd646`): the
  package's `tests/conftest.py` clears the host override providers for every
  package test. `test_spam.py` alone: 14 passed.
- **Item 10:** `_sole_video_url` passes `skip_code=True`, and the web
  `embedUrlOf` refuses a paragraph whose `<code>` holds text, matching the
  server.
- **Item 11: closed per the owner's decision (2026-09-28):** a card-only
  body keeps an empty excerpt. That was already the behavior; a test now pins
  it.
- **Item 13:** `sanitize_rich_text` sets `target="_blank"` on every body
  `<a>` via nh3's `set_tag_attribute_values` (owner: server-side). A
  client-sent `target` never survives. The package's nh3 floor rises to
  `>=0.2.12`, the first release with that argument (checked by grepping the
  0.2.11 and 0.2.12 wheels). Mentions are client-side `<span>`s and quote
  links come from the `post_quote` block, so neither gets a new tab. Posts
  stored before this keep same-tab links until edited; only test accounts
  exist. Three tests' expected anchor markup gained `target="_blank"`; these
  are deliberate test edits.
- **Mutation checks:** 6 of 6 caught (5 backend, 1 web). Each ran against a
  `cp` backup, was restored, and was confirmed with `cmp`.
- **Left for PR 2:** items 5 (a wall-clock deadline on the page fetch) and 12
  (log why a fetch failed). They change the SSRF-pinned fetcher, so they get
  their own review.

### 2026-10-09 - Items 5 and 12 fixed (PR 2 of 2, #972); todo archived

- **#971 merged** (PR 1: items 4, 6, 7, 10 and 13; 8 and 11 closed). Its
  round-1 review caught a regression the item-7 trim introduced: a card
  stored with a URL ending in punctuation was lost on edit. It now reuses
  the untrimmed URL when the stored body has a card for it. Round 2
  verified the fix.
- **Item 5:** `_fetch_html(target, deadline)` reuses the image download's
  watchdog and `read1` loop. The connect timeout and each redirect's DNS
  timeout are capped at the time left. The snapshot passes its budget
  through, and the composer endpoint gets
  `LINK_PREVIEW_PAGE_DEADLINE_SECONDS` (8 s). A failure caused by running
  out of OUR budget is not cached.
- **Item 12:** each fresh failure logs one
  `[LINK_PREVIEW] page fetch failed (<reason>) for host <host>` line. The
  log never includes the path or query, and a cached answer logs nothing.
  "No usable title" cannot happen, because the parser falls back to the
  domain.
- **Mutation checks:** 7 of 7 caught. The full backend suite: 4479 passed;
  the one failure is the known environment test.
- **Review:** neither PR had a blocking finding left. The non-blocking notes
  from both are in todo 535.
