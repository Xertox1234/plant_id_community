---
status: completed
priority: p4
issue_id: "344"
tags: [forum, package, wagtail, embeds]
dependencies: []
---

# Video/oEmbed support in forum posts via Wagtail EmbedBlock

## Problem

Forum bodies support heading/paragraph/quote/code/image only
(`wagtail_forum/blocks.py:13-30`). Gardeners share how-to videos constantly;
on every competing platform a YouTube link unfurls into an embed. Here a
video is a bare link.

## Findings

- No `embed`/`video` block in `ForumBodyBlock`; intro embeds are stripped
  by the sanitizer (`api/sanitize.py`) — 2026-09-04 backend catalog §2.5.
- Wagtail's canonical answer is `wagtail.embeds.blocks.EmbedBlock`
  (context7 `/wagtail/wagtail`, `docs/advanced_topics/embeds.md`):

  ```python
  from wagtail.embeds.blocks import EmbedBlock

  class BaseStreamBlock(StreamBlock):
      embed_block = EmbedBlock(help_text="Insert a URL to embed", icon="media")
  ```

- Provider allowlist is a host setting:

  ```python
  WAGTAILEMBEDS_FINDERS = [
      {"class": "wagtail.embeds.finders.oembed",
       "providers": [youtube, vimeo]},
  ]
  ```

## Recommended Action

1. **Package:** add `embed = EmbedBlock()` to `ForumBodyBlock` **behind** a
   `get_setting("ALLOW_EMBED_BLOCKS", False)` gate — the reusable package
   can't assume a host wants oEmbed (external lookups, iframes in XSS
   surface). Wagtail's own package precedent: features inert until
   configured.
2. **Sanitizer contract:** embed block values resolve to provider HTML via
   Wagtail's embed cache. Decide the API envelope shape: return
   `{"type": "embed", "value": {"url": ..., "html": ..., "provider_name": ...}}`
   with `html` marked **pre-sanitized provider HTML** — the web renderer
   must sandbox (iframe with `sandbox`/`referrerpolicy`) rather than
   DOMPurify-stripping it into nothing. Extend
   `tests/api/test_topic_create.py`'s escape-contract tests.
3. **Security posture:** host `WAGTAILEMBEDS_FINDERS` restricted to a
   short provider list (youtube, vimeo); embed HTML delivered only via the
   API envelope, never stored unsanitized raw inputs. Note in
   `docs/rules/security.md` / pattern doc if a new rule emerges.
4. **Web:** TipTap node or paste-handler that converts provider URLs into
   embed blocks on submit; render sandboxed iframe.
5. **Flutter:** render a thumbnail + external link tappable card; sandboxed
   WebView optional.

## Technical Details

- `wagtail_forum/blocks.py:13-30` — block registry; added block requires a
  package migration for the StreamField deconstruct (see migration 0004's
  block list).
- `wagtail_forum/api/sanitize.py:1-247` — sanitizer allowlist.
- Embed resolution is **cached by Wagtail** (embed cache) — no per-request
  provider calls; still wrap lookup in the API write path's error handling
  (offline providers must not 500 a post create).

## Acceptance Criteria

- [x] `EmbedBlock` available in forum bodies only when the package setting
      enables it; default keeps today's contract (package tests both ways)
- [x] Embed envelope shape documented + test-pinned in the escape-contract
      suite; offline/failed lookup degrades to a plain link, not a 500
- [x] Host provider allowlist committed (youtube/vimeo only)
- [x] Web renders sandboxed embeds; Flutter renders thumbnail card

## Work Log

### 2026-09-04 - Filed

- Surfaced by the 2026-09-04 forum competitive assessment (smaller-misses:
  no embeds/oEmbed). Wagtail API verified via context7 against
  `/wagtail/wagtail` (v7.3 docs, closest indexed to our 7.4.2).

### 2026-09-05 - Started by completing-todos skill (run 2026-09-05-0408)

- Picked up by automated workflow.

### 2026-09-05 - Design decisions (run 2026-09-05-0408)

- **Block declared unconditionally, gated at the API and on read.** A
  StreamField's block list is schema (migration 0031 alters `Post.body`),
  so `embed = EmbedBlock()` exists on every host; `WAGTAILFORUM_ALLOW_EMBED_
  BLOCKS` (default False) makes the API refuse it on write and the read
  envelope carry no player URL. A CMS-inserted embed on an opted-out host
  renders as a plain link. The provider allowlist is Wagtail's own
  `WAGTAILEMBEDS_FINDERS`; the host commits youtube + vimeo only
  (`test_host_allows_exactly_youtube_and_vimeo_embeds`).
- **Envelope deviates from the todo on purpose — no provider HTML.**
  `{url, provider_name, title, thumbnail_url, embed_url}`; `embed_url` is
  derived server-side from the ORIGINAL url with per-provider regexes
  (youtube-nocookie, player.vimeo) so the web renders its own sandboxed
  iframe and never injects provider markup (DOMPurify would strip an
  iframe into nothing — the todo's own warning; delivering pre-sanitized
  HTML anyway is XSS surface nobody renders). Unknown-but-allowed providers
  and opted-out hosts get `embed_url: null` → thumbnail/link card.
- **Network exactly once, at write time, bounded.** Wagtail's oEmbed finder
  calls `requests.get` with no timeout, so `warm_embed` runs the fetch on a
  worker thread under `WAGTAILFORUM_EMBED_FETCH_TIMEOUT_SECONDS` (5s) while
  the author waits; timeout/provider failure/finder bug all degrade to a
  link card and the post still saves. The worker closes its own DB
  connection. Reads are DB-only (`Embed` cache row), never `get_embed`.
- **Web composer:** no TipTap node — a paragraph that is only a YouTube/
  Vimeo link becomes an `embed` block on submit; re-editing round-trips
  through `<p><a href>url</a></p>`. **Flutter:** thumbnail card with
  provider/title/link, no WebView; tapping hands the URL to the renderer's
  existing `onOpenLink` (the thread screen surfaces it, url_launcher-free,
  exactly as paragraph links are handled — the flutter reviewer caught that
  this path already existed); a real launcher stays parity work (todo 341).

### 2026-09-05 - Verification evidence (run 2026-09-05-0408)

- AC1 gated block, default keeps today's contract:
  `test_embed_block_is_refused_on_write_until_the_host_opts_in` (setting
  False → 400, no topic), `test_legacy_embed_data_reads_as_a_plain_link_when_
  the_host_switches_embeds_off`; the block is in the schema (migration
  `0031_post_body_embed`), README rows for both new settings pass
  `test_docs`. Mutation check: gate removed → the refusal test fails.
- AC2 envelope documented + pinned; offline provider degrades:
  `test_embed_is_resolved_once_at_write_and_read_without_any_fetch` (exact
  envelope, no `html`, one fetch for a duplicate URL, finder patched to
  raise on the read), `test_an_unreachable_provider_still_saves_the_post_as_
  a_link_card` (201 + link card), `test_embed_envelope_reads_the_cache_row_
  and_never_fetches`, `test_warm_embed_caches_the_row_and_swallows_provider_
  failure_and_timeout` (returns inside a 0.05 s bound), the regex table incl.
  an injection attempt. Mutation check: write-time warm removed → the
  resolved-once test fails.
- AC3 host allowlist: `settings.py` `WAGTAILEMBEDS_FINDERS` youtube + vimeo,
  pinned by `apps/forum_host/tests/test_embed_providers.py`.
- AC4 web sandboxed embeds + Flutter card: `StreamFieldRenderer.test.tsx` +2
  (sandboxed iframe on the server URL; link card when none),
  `forumBody.test.ts` +3 (URL-only paragraph → embed; prose link stays
  text; round trip), `forum_body_block_test.dart` +1, `forum_body_renderer_
  test.dart` +1 (card, no player).
- Evidence: embed suites `22 passed`; adjacent body/docs `43 passed`; full
  backend suite `2131 passed, 8 skipped in 306.19s`; web tsc/eslint/prettier
  clean, full web suite `1100 passed (90 files)`; Flutter `23 passed`,
  `flutter analyze` clean.

### 2026-09-05 - Code review round 1: kimi, flutter, react (run 2026-09-05-0408)

- kimi-review (backend diff): 1 CRITICAL — false positive: it claimed the
  tests' `get_finder_for_embed` patch returns the wrong type, but in
  Wagtail 7.4 that helper RETURNS the finder's embed dict (verified in
  `wagtail/embeds/embeds.py`), and the tests assert the cached row exists.
  WARNING repaired — the read path did one `Embed` query per embed block
  (an N+1 across a page): `cached_embeds_for()` + `build_forum_embed_map()`
  now batch one query per page through the same context path as the image
  map, threaded into the post list, the edit response and revision
  snapshots; pinned by `test_post_list_query_count_is_flat_across_embed_
  bearing_posts` (1 vs 5 embed posts equal; embeds OFF costs one query
  less). WARNING repaired — host-mount read test
  (`test_embed_blocks_ship_through_the_host_mount_as_envelopes`, which also
  pins the host default ON). WARNING n/a — the React renderer case IS in
  this diff (kimi saw the backend half). SUGGESTION declined — a shared
  executor would let one stuck provider thread block every later fetch
  behind it; per-call executors isolate a hang to its own post.
- flutter-dart — nothing blocking; MEDIUM ×3 repaired: the renderer
  already threads `onOpenLink` (the thread screen surfaces links in a
  SnackBar without url_launcher), so the card is now tappable through it
  (`tapping an embed card hands its URL to onOpenLink`); a blank envelope
  renders the "Video unavailable" placeholder instead of an empty card;
  the `EmbedBlock` class was sitting between `DeletedImageBlock`'s doc
  comment and its declaration — moved. LOW ×3 repaired: thumbnail loading
  placeholder, doc list, consistent fallback icon; INFO: `excludeSemantics`
  so the composed label is not double-announced.
- react-typescript — nothing blocking; MEDIUM repaired: `bodyBlocksToHtml`
  builds a raw `<a href>` string that bypasses React's href guard, so a
  persisted non-http(s) embed URL is now dropped on re-edit (test); LOW
  repaired: the link card uses the file's `getSafeHref()`; LOW repaired:
  `youtube.com/live/` share links accepted (regex on both web and server,
  test rows on both).

### 2026-09-05 - Review round 2: django-drf + cross-cutting reviewers (run 2026-09-05-0408)

Dispatched read-only; findings and disposition:

- **[high, both] `warm_embed` bound only the CALLER** — Wagtail's `OEmbedFinder`
  calls `requests.get` with no timeout, so a stalled provider kept the worker
  thread (and its DB connection) alive past `.result(timeout=)`; a pool was
  also created per call (the anti-pattern in `services.md`). **Repaired:**
  `TimeoutOEmbedFinder` (subclass the host registers in
  `WAGTAILEMBEDS_FINDERS`) passes `EMBED_FETCH_TIMEOUT_SECONDS` as a real
  socket timeout — which also bounds the Wagtail admin embed chooser (the
  cross-cutting `medium`, a second write surface outside the API wrapper);
  `warm_embeds(urls)` runs on a shared, bounded, lazily-created pool and
  resolves a body's URLs concurrently inside ONE window, logging late
  outcomes via a done-callback instead of dropping them.
- **[high cross-cutting / medium django] no cap on embed URLs per body** —
  `MAX_BODY_BLOCKS` allowed 100 sequential fetches. **Repaired:**
  `MAX_EMBED_URLS_PER_BODY` (default 5, README row) → 400 before any fetch;
  with the concurrent warm-up the wait is one window regardless.
- **[medium django] `is_supported_url` accepted `"><script>` tails** (the
  provider regexes end in `.+$`). **Repaired:** RFC 3986 character class
  check; the web/Flutter renderers already escaped, so belt-and-braces.
- **[medium cross-cutting] unreachable-provider test read outside the
  no-fetch patch.** **Repaired:** wrapped like its siblings.
- **[high, both] serializer N+1 per embed block** — already batched
  (`build_forum_embed_map`) in the on-disk state the reviewers partly saw
  unstaged; staged together with the views wiring in this commit.
- **[low django] dead `cache_clear()` expression in a test** — removed
  (Wagtail's `setting_changed` receiver clears `get_finders`).

Evidence after repair:

```text
$ pytest test_embeds.py test_embeds_api.py test_embed_providers.py test_docs.py test_api_mounted.py -k "embed or docs"
30 passed, 9 deselected
```

Note: a full-suite run launched alongside targeted `--create-db` runs
reported 962 errors of `database "test_plant_community" does not exist` —
the concurrent-pytest artifact from memory, not failures; re-run alone
(evidence below).

Final full backend suite (alone, `--create-db`):

```text
2137 passed, 8 skipped, 5 warnings in 257.11s (0:04:17)
```

### 2026-09-05 - Completed by completing-todos skill (run 2026-09-05-0408)

- Verification: all acceptance criteria evidenced (backend 2137 passed / web 1101 passed / flutter analyze clean).
- Review: kimi + react + flutter + django-drf + cross-cutting, 2 rounds; every high/medium repaired (finder socket timeout, shared pool + one wait window, per-body cap, URL charset, page-batched Embed map, http(s)-only href, tappable Flutter card).
