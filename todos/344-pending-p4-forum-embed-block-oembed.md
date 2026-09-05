---
status: pending
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

- [ ] `EmbedBlock` available in forum bodies only when the package setting
      enables it; default keeps today's contract (package tests both ways)
- [ ] Embed envelope shape documented + test-pinned in the escape-contract
      suite; offline/failed lookup degrades to a plain link, not a 500
- [ ] Host provider allowlist committed (youtube/vimeo only)
- [ ] Web renders sandboxed embeds; Flutter renders thumbnail card

## Work Log

### 2026-09-04 - Filed

- Surfaced by the 2026-09-04 forum competitive assessment (smaller-misses:
  no embeds/oEmbed). Wagtail API verified via context7 against
  `/wagtail/wagtail` (v7.3 docs, closest indexed to our 7.4.2).
