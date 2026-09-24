---
status: pending
priority: p3
issue_id: "426"
tags: [forum, backend, embeds, spam]
dependencies: []
---

# Spam text extraction renders embed blocks through the provider

## Problem

`wagtail_forum/spam/base.py::extract_text` flattens a post body with
`str(getattr(block, "value", ""))`. For an `embed` block, the value is a
Wagtail `EmbedValue`, and `EmbedValue.__str__` returns `self.html`, which is
`embed_to_frontend_html(url)` → `get_embed(url)`.

- If the embed cache has a fresh row (the usual case, since
  `validate_forum_body` warms it at write time), this is one DB read and
  returns the provider's iframe HTML.
- If it does not (the warm-up timed out, or the provider failed), this is a
  **second provider fetch inside the request**. It happens during spam
  screening, bounded only by `TimeoutOEmbedFinder`'s timeout. That breaks
  the rule in `embeds.py` that the network is touched once, at write time,
  and bounded.
- The text screened is provider HTML, not what the author wrote.

This was already true for explicit embed blocks from the web composer
(todo 344). Todo 421 (server-side conversion) sends every mobile video link
down this path too.

## Findings

- The only callers are the spam backends (`spam/base.py`,
  `spam/heuristic.py`, and the host's LLM backend through `check_text`).
  Mention resolution does NOT use it: `mentions.py` has its own walker,
  `_mention_scan_text`, which reads `raw_data` and runs `strip_tags`.
- Hypothesis, not verified: the LLM spam backend receives the iframe HTML
  as part of its prompt text.

## Recommended Action

In `extract_text`, flatten an `embed` block as its URL
(`block.value.url`), never `str(block.value)`. Pin it with a test showing
that extracting text from a post with an embed block makes no finder call
(patch `wagtail.embeds.embeds.get_finder_for_embed` to raise) and includes
the URL.

## Acceptance Criteria

- [ ] `extract_text` on a body with an `embed` block does not call the
      finder. Pinned by a test that fails before the change.
- [ ] The URL is in the extracted text, so the link-count heuristic still
      counts it.

## Work Log

### 2026-09-24 - Filed while implementing todo 421
